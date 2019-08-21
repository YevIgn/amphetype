This is actually my fork of somebody else's fork of 'my fork of amphetype'.

This fork hacks in python 3 compatibility.  I did it quickly and carelessly and
probably missed a bunch of things.  Email me at jjl@pobox.com if you hit a
problem.  To run it:

* make a python 3 virtualenv (python -m venv ~/my/virtualenvs/amphetype)
* activate the virtualenv (source ~/my/virtualenvs/amphetype/bin/activate)
* in the root directory of this git repository, install: pip install -e .
* python -c 'import Amphetype'

To run it a second time, you don't need to do the first or third steps, so:

* activate the virtualenv (source ~/my/virtualenvs/amphetype/bin/activate)
* python -c 'import Amphetype'



amphetype is lovely, thank you tristesse!


-oOo- the next guy's readme starts here -oOo-


My Fork of Amphetype - A great typing program.
It contains a bunch of small improvements that I needed to use it.

These include:
 * Phrase based lesson
 * Forced addition of capitals and symbols to words ( to strength training of these if so desired)
 * improved lesson splitter
 * permissive mode
 * etc 
 
Sample text included:
 * Selections from project gutenberg
 * All the typing tests from TyperRacer.com
 * QWERTY right hand / Left Hand and alternating hand words


To run, type:

python Amphetype.py


Depends on:

python-qt4  (that is, PyQt 4.3+)

OPTIONAL: py-editdist from http://www.mindrot.org/projects/py-editdist/
 - This latter dependancy is by no means critical and you will
 probably never get to use it. (For fetching words from a wordfile
 that are "similar" to your target words in the lesson generator.)
 If you don't have the module it will just select random words
 instead



