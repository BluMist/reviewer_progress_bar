# -*- coding: utf-8 -*-

"""
Anki Add-on: Reviewer Answer Overhaul

Combines the following add-ons...

- Answer Key Remap, (c) fisheggs
- Handy Answer Keys Shortcuts, (c) Vitalie Spinu
- Ignore Space/Enter When Answer Shown, (c) Damien Elmes
- Answer Confirmation, (c) Albert Lyubarsky
- Refocus Card When Reviewing, (c) Edgar Simo-Sierra
- Button Colours Good Again, (c) Calumks
- More Buttons for New Cards, (c) Steve AW

...and applies a number of customizations specific to my workflow.

Also includes code from the following add-ons:

- Gamepad add-on (custom tooltips), (c) tmbb

Copyright: (c) Glutanimate 2016-2017
License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
""" 

import sys
reload(sys)  
sys.setdefaultencoding('utf8')

from aqt.qt import *
from aqt import mw
from aqt.reviewer import Reviewer
from anki.hooks import wrap, addHook
from anki.lang import _
from aqt.utils import tooltip

# USER CONFIGURATION START

# answer key mapping to ease. numbers correspond to key index
remap = { 2:  [None, 1, 1, 2, 2],    # nil     Again   Again   Good    Good
          3:  [None, 1, 1, 2, 3],    # nil     Again   Again   Good    Easy
          4:  [None, 1, 2, 3, 4]}    # nil     Again   Hard    Good    Easy

# color assignment to buttons and tooltips
colors = {
    _("Again"): "#D32F2F",
    _("Hard"): "#455A64",
    _("Good"): "#4CAF50",
    _("Easy"): "#03A9F4"
}

# answer key definition
ease_keys = {
    "1": 1, "j": 1, # Again
    "2": 2, "k": 2, # Hard
    "3": 3, "l": 3, # Good
    "4": 4, u"ö": 4 # Easy
}

# extra buttons for new cards and cards in learning
extra_buttons = [{"label": "+" + _("Easy"), "color": "#0292D3", "hotkeys": ("5", "p"), "factor": 1.5},
                 {"label": "++" + _("Easy"), "color": "#0276AB", "hotkeys": ("6", u"ü"), "factor": 3},
                 {"label": "+++" + _("Easy"), "color": "#015276", "hotkeys": ("7", "+"), "factor": 4.5}]

# fuzzing level, set this to 0 to disable fuzzing on rescheduling
RESCH_FUZZING_IVL = 3

# USER CONFIGURATION END

#Anki uses a single digit to track which button has been clicked.
#We will use 6 and above to track the extra buttons.
INTERCEPT_EASE_BASE = 6
#Must be four or less
assert len(extra_buttons) <= 4


### Tooltips

_tooltipTimer = None
_tooltipLabel = None

def custom_tooltip(msg, period=3000, color="#feffc4", textcolor="#000000",
                   parent=None, x=None, y=None):
    global _tooltipTimer, _tooltipLabel
    class CustomLabel(QLabel):
        def mousePressEvent(self, evt):
            evt.accept()
            self.hide()
    closeTooltip()
    aw = parent or mw.app.activeWindow() or mw
    lab = CustomLabel("""\
<table cellpadding=10>
<tr>
<td>%s</td>
</tr>
</table>""" % msg, aw)
    lab.setFrameStyle(QFrame.Panel)
    lab.setLineWidth(2)
    lab.setWindowFlags(Qt.ToolTip)
    p = QPalette()
    p.setColor(QPalette.Window, QColor(color))
    p.setColor(QPalette.WindowText, QColor(textcolor))
    lab.setPalette(p)
    if x == "center":
        pt_x = (aw.width() - lab.width()) / 2
    else:
        pt_x = x or 0
    if y == "center":
        pt_y = (aw.height() - lab.height()) / 2
    else:
        pt_y = y or -100 + aw.height() 
    lab.move(
        aw.mapToGlobal(QPoint(pt_x, pt_y)))
    lab.show()
    _tooltipTimer = mw.progress.timer(
        period, closeTooltip, False)
    _tooltipLabel = lab

def closeTooltip():
    global _tooltipLabel, _tooltipTimer
    if _tooltipLabel:
        try:
            _tooltipLabel.deleteLater()
        except:
            # already deleted as parent window closed
            pass
        _tooltipLabel = None
    if _tooltipTimer:
        _tooltipTimer.stop()
        _tooltipTimer = None

### Reviewer key handler

def keyHandler(self, evt, _old):
    key = unicode(evt.text())
    state = self.state
    # disable space/return on answer screen:
    if (key == " " or evt.key() in (Qt.Key_Return, Qt.Key_Enter)) and state == "answer":
        return
    # z as a standin for ctrl+z
    elif key == "z":
        try:
            self.mw.onUndo()
        except TypeError: # nothing more to undo
            pass
    # custom key definitions for QWERTZ keyboard layout
    elif key == "m":
        self.onMark()
    elif key == "#":
        self.onBuryNote()
    elif key == "\"":
        self.onSuspendCard()
    # custom answer keys
    elif key in ease_keys:
        if self.state == "question":
            self._showAnswerHack()
        else:
            ease = ease_keys[key]
            self._answerCard(ease)
    else:
        # extra buttons:
        if self.state == "answer":
            for idx, btn in enumerate(extra_buttons):
                if key in btn["hotkeys"]:
                    return self._answerCard(idx + INTERCEPT_EASE_BASE)
        return _old(self, evt)


### Answer button generation

button_html = '''
<td align=center>%s
<button %s title="%s" onclick='py.link("ease%d");'
style='color: %s;'>%s</button>
</td>'''

def generateButton(self, ease, label):
    default = self._defaultEase()
    if ease == default:
        extra = "id=defease"
    else:
        extra = ""
    due = self._buttonTime(ease)
    return button_html % (due, extra, _("Shortcut key: %s") % ease, 
                          ease, colors[label], label)

def myAnswerButtons(self):
    times = []
    buf = "<center><table cellpading=0 cellspacing=0><tr>"
    for ease, label in self._answerButtonList():
        buf += self._generateButton(ease, label)

    # More buttons:
    #Only for cards in the new queue
    if self.card.type in (0, 1, 3): # New, Learn, Day learning
        #Check that the number of answer buttons is as expected.
        assert self.mw.col.sched.answerButtons(self.card) == 3
        easyivl = self.mw.col.decks.confForDid(self.card.did)['new']['ints'][1]
        showdue = self.mw.col.conf['estTimes']
        for idx, btn in enumerate(extra_buttons):
            low = int(round(easyivl * btn["factor"]))
            up = low + int(round(RESCH_FUZZING_IVL * btn["factor"] * 0.25))
            ease = idx + INTERCEPT_EASE_BASE
            if showdue:
                due = "<span class=nobold>{0}–{1}d</span><br>".format(low, up)
            else:
                due = "<div class=spacer></div>"
            buf += button_html % (due, "", "/".join(btn["hotkeys"]),
                                  ease, btn["color"], btn["label"])
    buf += "</tr></table>"
    script = """
<script>$(function () { $("#defease").focus(); });</script>"""
    return buf + script


### Answering

def myAnswerCard(self, actual_ease, _old):
    # More answer buttons start
    ease = actual_ease
    was_new_card = self.card.type in (0, 1, 3)
    is_extra_button = was_new_card and actual_ease >= INTERCEPT_EASE_BASE
    if is_extra_button:
        #Make sure this is as expected.
        assert self.mw.col.sched.answerButtons(self.card) == 3
        #So this is one of our buttons. First answer the card as if "Easy" clicked.
        ease = 4 # 4 because of answer key remap
        prev_card = self.card #We will need this to reschedule it.

    # Remap keys to eases
    count = self.mw.col.sched.answerButtons(self.card) # Get button count
    try:
        ease = remap[count][ease]
    except (KeyError, IndexError):
        pass

    # Answer confirmation color
    if actual_ease < INTERCEPT_EASE_BASE:
        answers = self._answerButtonList()
        answer = answers[ease-1][1]
        color = colors[answer]
        msg = answer

    ret = _old(self, ease)

    # More answer buttons:
    if is_extra_button:
        btn = extra_buttons[actual_ease - INTERCEPT_EASE_BASE]
        easyivl = self.mw.col.decks.confForDid(prev_card.did)['new']['ints'][1]
        low = int(round(easyivl * btn["factor"]))
        up = low + int(round(RESCH_FUZZING_IVL * btn["factor"] * 0.25))
        self.mw.col.sched.reschedCards([prev_card.id], low, up)
        msg = u"<center>Rescheduled: <br>{0}–{1} days</center>".format(low, up)
        color = btn["color"]
        custom_tooltip(msg, period=1000, color=color, textcolor="#FFFFFF")

    # Answer confirmation color

    if not self.card: # cards finished, back on overview screen
        custom_tooltip(msg, period=1000, color=color, textcolor="#FFFFFF")

    self.bottom.web.eval("""
        document.body.style.background = "-webkit-gradient(linear, left top, left bottom, from(#fff), to(%s))";
        setTimeout(function(){
            document.body.style.background = "-webkit-gradient(linear, left top, left bottom, from(#fff), to(#ddd))";
        }, 1000);
        """ % color)
    return ret


def interface_refocus():
   mw.web.setFocus()


### Hooks and patches

Reviewer._generateButton = generateButton
Reviewer._answerButtons = myAnswerButtons
Reviewer._keyHandler = wrap(Reviewer._keyHandler, keyHandler, "around")
Reviewer._answerCard = wrap(Reviewer._answerCard, myAnswerCard, "around")

addHook("showQuestion", interface_refocus)
addHook("showAnswer", interface_refocus)