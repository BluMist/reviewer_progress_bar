 # -*- coding: utf-8 -*-

"""
Anki Add-on: Custom Tag Editor

Various modifications to the tag editor:

- disable initial popup when entering tag editor
- apply current completion with Enter/Return
- go to next completion with Ctrl+Tab
- show completer with Up/Down arrows

Copyright: (c) Glutanimate 2016-2017
License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""

from aqt.qt import *
from aqt.tagedit import TagEdit

def myFocusInEvent(self, evt):
    # don't show completer by default
    QLineEdit.focusInEvent(self, evt)

def myKeyPressEvent(self, evt):
    if evt.key() in (Qt.Key_Up, Qt.Key_Down):
        # show completer on up/down
        if not self.completer.popup().isVisible():
            self.showCompleter()
        return
    if (evt.key() == Qt.Key_Tab and evt.modifiers() == Qt.ControlModifier
      and self.completer.popup().isVisible()):
        # select next completion
        index = self.completer.currentIndex()
        self.completer.popup().setCurrentIndex(index)
        start = self.completer.currentRow()
        if not self.completer.setCurrentRow(start + 1):
            self.completer.setCurrentRow(0)
        return
    if evt.key() in (Qt.Key_Enter, Qt.Key_Return):
        # set current completion
        popidx = self.completer.popup().currentIndex()
        selected = QCompleter.pathFromIndex(self.completer, popidx)
        if not selected:
            # only apply completion if no list item selected:
            self.applyCompletion()
        self.hideCompleter()
        QWidget.keyPressEvent(self, evt)
        return
    QLineEdit.keyPressEvent(self, evt)
    if not evt.text():
        # if it's a modifier, don't show
        return
    if evt.key() not in (
        Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Space,
        Qt.Key_Tab, Qt.Key_Backspace, Qt.Key_Delete):
        self.showCompleter()

def applyCompletion(self):
    txt = self.text()
    pos = self.cursorPosition()
    tags = txt.split()
    after = txt[pos:].split()
    before = txt[:pos].split()
    try:
        cur = txt[pos]
        if cur == " ": # cur is at tag boundary
            after = None
    except IndexError:
        pass
    if not before and after:
        pfx = after[0]
    elif not after and before:
        pfx = before[-1]
    elif before != after:
        pfx = before[-1] + after[0]
    else:
        pfx = before[0]
    tidx = tags.index(pfx)
    self.completer.setCompletionPrefix(pfx)
    completion = self.completer.currentCompletion()
    if not completion:
        return False
    if completion not in tags:
        tags[tidx] = completion + " "
    else:
        tags[tidx] = ""
    self.setText(" ".join(tags))
    newpos = len(" ".join(tags[:tidx+1]))
    self.setCursorPosition(newpos)
    return True

TagEdit.applyCompletion = applyCompletion
TagEdit.focusInEvent = myFocusInEvent
TagEdit.keyPressEvent = myKeyPressEvent
