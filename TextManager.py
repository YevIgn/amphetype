from __future__ import with_statement, division

import os.path as path
import time
import hashlib
import re

from Text import LessonMiner
from Data import DB
from QtUtil import *
from Config import *

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class SourceModel(AmphModel):
    def signature(self):
        self.hidden = 1
        return (["Source", "Length", "Results", "WPM", "Dis."],
                [None, None, None, "%.1f", None])

    def populateData(self, idxs):
        if len(idxs) == 0:
            return list(map(list, DB.fetchall("""
            select s.rowid, s.name, t.count, r.count, r.wpm, ifelse(nullif(t.dis, t.count), 'No', 'Yes')
                    from source as s
                    left join (select source, count(*) as count, count(disabled) as dis from text group by source) as t
                        on (s.rowid = t.source)
                    left join (select source, count(*) as count, avg(wpm) as wpm from result group by source) as r
                        on (t.source = r.source)
                    where s.disabled is null
                    order by s.name""")))

        if len(idxs) > 1:
            return []

        r = self.rows[idxs[0]]

        return list(map(list, DB.fetchall("""select t.rowid, substr(t.text, 0, 40)||"...", length(t.text), r.count, r.m, ifelse(t.disabled, 'Yes', 'No')
                from (select rowid, * from text where source = ?) as t
                left join (select text_id, count(*) as count, agg_median(wpm) as m from result group by text_id) as r
                    on (t.id = r.text_id)
                order by t.rowid""", (r[0], ))))

class TextManager(QWidget):

    defaultText = ("", 0, """Welcome to Amphetype!
A typing program that not only measures your speed and progress, but also gives you detailed statistics about problem keys, words, common mistakes, and so on. This is just a default text since your database is empty. You might import a novel or text of your choosing and text excerpts will be generated for you automatically. There are also some facilities to generate lessons based on your past statistics! But for now, go to the "Sources" tab and try adding some texts from the "txt" directory.""")


    def __init__(self, *args):
        super(TextManager, self).__init__(*args)

        self.diff_eval = lambda x: 1
        self.model = SourceModel()
        tv = AmphTree(self.model)
        tv.resizeColumnToContents(1)
        tv.setColumnWidth(0, 300)
        self.connect(tv, SIGNAL("doubleClicked(QModelIndex)"), self.doubleClicked)
        self.tree = tv

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()

        self.setLayout(AmphBoxLayout([(["Below you will see the different text sources used. Disabling texts or sources deactivates them so they won't be selected for typing. You can double click a text to do that particular text.\n",
                        (self.tree, 1),
                        self.progress,
                        [AmphButton("Import Texts", self.addFiles), None,
                            AmphButton("Enable All", self.enableAll),
                            AmphButton("Delete Disabled", self.removeDisabled), None,
                            AmphButton("Update List", self.update)],
                        [#AmphButton("Remove", self.removeSelected), "or",
                            AmphButton("Toggle disabled", self.disableSelected),
                            "on all selected texts that match <a href=\"http://en.wikipedia.org/wiki/Regular_expression\">regular expression</a>",
                            SettingsEdit('text_regex')],
                          [AmphButton("Toggle All selected", self.disableAllSelected), "Disabled items won't be selected in order"]], 1),
                    [["Selection method for new lessons:",
                            SettingsCombo('select_method', ['Random', 'In Order', 'Difficult', 'Easy']), None],
                        "(in order works by selecting the next text after the one you completed last, in the order they were added to the database, easy/difficult works by estimating your WPM for several random texts and choosing the fastest/slowest)\n",
                        20,
                        AmphGridLayout([[("Repeat <i>texts</i> that don't meet the following requirements:\n", (1, 3))],
                            ["WPM:", SettingsEdit("min_wpm")],
                            ["Accuracy:", SettingsEdit("min_acc"), (None, (0, 1))],
                            [("Repeat <i>lessons</i> that don't meet the following requirements:\n", (1, 3))],
                            ["WPM:", SettingsEdit("min_lesson_wpm")],
                            ["Accuracy:", SettingsEdit("min_lesson_acc")], ]),
                        None]], QBoxLayout.LeftToRight))

        self.connect(Settings, SIGNAL("change_select_method"), self.setSelect)
        self.setSelect(Settings.get('select_method'))
        self.cur = None

    def setSelect(self, v):
        if v == 0 or v == 1:
            self.diff_eval = lambda x: 1
            self.nextText()
            return

        hist = time.time() - 86400.0 * Settings.get('history')
        tri = dict(DB.execute("""
                    select data, agg_median(time) as wpm from statistic
                    where w >= ? and type = 1
                    group by data""", (hist, )).fetchall()) #[(t, (m, c)) for t, m, c in

        g = tri.values()
        if len(g) == 0:
            return lambda x: 1
        g.sort(reverse=True)
        expect = g[len(g) // 4]
        def _func(v):
            text = v[2]
            v = 0
            s = 0.0
            for i in range(0, len(text) - 2):
                t = text[i: i + 3]
                if t in tri:
                    s += tri[t]
                else:
                    #print "|", t,
                    s += expect
                    v += 1
            avg = s / (len(text) - 2)
            #print text
            #print " v=%d, s=%f" % (v, 12.0/avg), "ex:", expect
            return 12.0 / avg

        self.diff_eval = _func
        self.nextText()

    def addFiles(self):

        qf = QFileDialog(self, "Import Text From File(s)")
        qf.setFilters(["UTF-8 text files (*.txt)", "All files (*)"])
        qf.setFileMode(QFileDialog.ExistingFiles)
        qf.setAcceptMode(QFileDialog.AcceptOpen)

        self.connect(qf, SIGNAL("filesSelected(QStringList)"), self.setImpList)

        qf.show()

    def setImpList(self, files):
        self.sender().hide()
        self.progress.show()
        for x in map(str, files):
            self.progress.setValue(0)
            fname = path.basename(x)
            lm = LessonMiner(x)
            self.connect(lm, SIGNAL("progress(int)"), self.progress.setValue)
            self.addTexts(fname, lm, update=False)

        self.progress.hide()
        self.update()
        DB.commit()

    def addTexts(self, source, texts, lesson=None, update=True):
        source = source +' Length:' + str(Settings.get('min_chars'))
        id = DB.getSource(source, lesson)

        r = []
        for x in texts:
            x = self.cleanText(x)
            h = hashlib.sha1()
            h.update(x.encode('utf-8'))
            txt_id = h.hexdigest()
            dis = 1 if lesson == 2 else None
            try:
                DB.execute("insert into text (id, text, source, disabled) values (?, ?, ?, ?)", (txt_id, x, id, dis))
            except Exception:
                pass # silently skip ...
        r.append(txt_id)
        if update:
            self.update()
        if lesson:
            DB.commit()
        return r

    def cleanText(self, x):
        strip = Settings.get('sentence_strip')
        if len(strip) != 0:
            x = re.sub(Settings.get('sentence_strip'), ' ', x)
        # extra spaces
        x = re.sub('[ ]{2,}', ' ', x, flags=re.MULTILINE)
        # windows line endings
        x = re.sub('\r', '', x, flags=re.MULTILINE)
        # space on newline
        x = re.sub('\n\s', '\n', x, flags=re.MULTILINE)
        return x

    def newReview(self, review):
        q = self.addTexts("<Reviews>", [review], lesson=2, update=False)
        if q:
            v = DB.fetchone("select id, source, text from text where id = ?", self.defaultText, q)
            print("### v %s" % (v, ))
            self.emit(SIGNAL("setText"), v)
        else:
            self.nextText()

    def update(self):
        self.emit(SIGNAL("refreshSources"))
        self.model.reset()



    def nextText(self):
        if  Settings.get('repeat'):
            self.lastText()
        else:
            type = Settings.get('select_method')

            if type != 1:
                # Not in order
                v = DB.execute("select id, source, text from text where disabled is null order by random() limit %d" % Settings.get('num_rand')).fetchall()
                if len(v) == 0:
                    v = None
                elif type == 2:
                    v = min(v, key=self.diff_eval)
                elif type == 3:
                    v = max(v, key=self.diff_eval)
                else:
                    v = v[0] # random, just pick the first
            else:
                # Fetch in order
                lastid = (0, )
                lastResultGuid = DB.fetchone("""select r.text_id
                    from result as r left join source as s on (r.source = s.rowid)
                    where (s.discount is null) or (s.discount = 1) order by r.w desc limit 1""", None)
                print("### lastResultGuid %s" % (lastResultGuid, ))
                if lastResultGuid is not None:
                    lastid = DB.fetchone("select rowid from text where id = ?", lastid, lastResultGuid)
                print("### lastid %s" % (lastid, ))
                v = DB.fetchone("select id, source, text from text where rowid > ? and disabled is null order by rowid asc limit 1", None, lastid)

            if v is None:
                v = self.defaultText
                print("### v2 %s" % (v, ))
            self.emit(SIGNAL("setText"), v)

    def lastText(self):
        # Fetch in order
        lastResultGuid = DB.fetchone("""select r.text_id
            from result as r left join source as s on (r.source = s.rowid)
            where (s.discount is null) or (s.discount = 1) order by r.w desc limit 1""", None)
        if lastResultGuid is not None:
            v = DB.fetchone("select id, source, text from text where id = ?", None, lastResultGuid)
        else:
            v = self.defaultText
            print("### v3 %s" % (v, ))

        if v is None:
            v = self.defaultText
            print("### v4 %s" % (v, ))

        self.emit(SIGNAL("setText"), v)

    def removeUnused(self):
        DB.execute('''
            delete from source where rowid in (
                select s.rowid from source as s
                    left join result as r on (s.rowid=r.source)
                    left join text as t on (t.source=s.rowid)
                group by s.rowid
                having count(r.rowid) = 0 and count(t.rowid) = 0
            )''')
        DB.execute('''
            update source set disabled = 1 where rowid in (
                select s.rowid from source as s
                    left join result as r on (s.rowid=r.source)
                    left join text as t on (t.source=s.rowid)
                group by s.rowid
                having count(r.rowid) > 0 and count(t.rowid) = 0
            )''')
        self.emit(SIGNAL("refreshSources"))

    def removeDisabled(self):
        DB.execute('delete from text where disabled = 1')
        self.removeUnused()
        self.update()
        DB.commit()

    def enableAll(self):
        DB.execute('update text set disabled = null where disabled is not null')
        self.update()

    def disableSelected(self):
        cats, texts = self.getSelected()
        DB.setRegex(Settings.get('text_regex'))
        DB.executemany("""update text set disabled = ifelse(disabled, NULL, 1)
                where rowid = ? and regex_match(text) = 1""",
                       map(lambda x: (x, ), texts))
        DB.executemany("""update text set disabled = ifelse(disabled, NULL, 1)
                where source = ? and regex_match(text) = 1""",
                       map(lambda x: (x, ), cats))
        self.update()

    def disableAllSelected(self):
        cats, texts = self.getSelected()
        DB.setRegex(Settings.get('text_regex'))
        DB.executemany("""update text set disabled = ifelse(disabled, NULL, 1) where rowid = ?""", map(lambda x: (x, ), texts))
        DB.executemany("""update text set disabled = ifelse(disabled, NULL, 1) where source = ?""", map(lambda x: (x, ), cats))
        self.update()

    def getSelected(self):
        texts = []
        cats = []
        for idx in self.tree.selectedIndexes():
            if idx.column() != 0:
                continue
            if idx.parent().isValid():
                texts.append(self.model.data(idx, Qt.UserRole)[0])
            else:
                cats.append(self.model.data(idx, Qt.UserRole)[0])
        return (cats, texts)

    def doubleClicked(self, idx):
        p = idx.parent()
        if not p.isValid():
            return

        q = self.model.data(idx, Qt.UserRole)
        v = DB.fetchall('select id, source, text from text where rowid = ?', (q[0], ))

        if len(v) <= 0:
            print("### v6 %s" % (v, ))
        self.cur = v[0] if len(v) > 0 else self.defaultText
        self.emit(SIGNAL("setText"), self.cur)
        self.emit(SIGNAL("gotoText"))
