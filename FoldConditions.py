import sublime, sublime_plugin
import collections, re, functools

Defines = []
MaxStack = 100

#def dbgprint ( *aArgs ) :
#  print(*aArgs)

def Defined( aWord, TestDigit = True ) :
  '''Determine if the given word is in our define list.  If it's a non-0
    numbers return true.'''
#  dbgprint(aWord)
  if aWord.isdigit() :
    #TestDigit false means we don't consider digits so we always return True.
    return True if not TestDigit else (aWord != "0")
  return aWord in Defines

def AddWord( aWord ) :
  '''Add a word if it is not defined.'''
  global Defines
  #Don't ever add digits.
  res =  not Defined(aWord, False)
  if res :
    Defines.append(aWord)
#    dbgprint(Defines)
  return res

def ToggleWord( aWord ) :
  '''If word is in the def list remove, otherwise add.'''
  global Defines
  if Defined(aWord, False) :
    try:
      Defines.remove(aWord)
    except:
      return False
  else:
    Defines.append(aWord)
  return True

def RemoveWord( aWord ) :
  '''Remove given word from the def list.'''
  global Defines
  try:
    Defines.remove(aWord)
#    dbgprint(Defines)
    return True
  except:
    return False

#Create enum for define parsing condition
#defon = In a define state with a true condition.
#defoff = In a define state with a false condition.
defon, defoff = range(2)

def OpOr( aValue1, aValue2 ) :
  # print("{} or {}".format(aValue1, aValue2))
  return aValue1 or aValue2

def OpAnd( aValue1, aValue2 ) :
  # print("{} and {}".format(aValue1, aValue2))
  return aValue1 and aValue2

#List of conditions for multiple defined() checks on a single line.
#1st number is True for defined, False for !defined.
moredefA = [
(True, re.compile("[ \t]*\|\|[ \t]*defined[ \t]*\((\w+)\)(.*)"), OpOr),
(False, re.compile("[ \t]*\|\|[ \t]*![ \t]*defined[ \t]*\((\w+)\)(.*)"), OpOr),
(True, re.compile("[ \t]*&&[ \t]*defined[ \t]*\((\w+)\)(.*)"), OpAnd),
(False, re.compile("[ \t]*&&[ \t]*![ \t]*defined[ \t]*\((\w+)\)(.*)"), OpAnd),
]

#List of #if expressions.
ifdefA = [
(True, re.compile("^[ \t]?#[ \t]*if(?P<df>def)?[ \t]*(?(df)|(defined))[ \t]*\(? ?(\w+)\)?(.*)")),
(False, re.compile("^[ \t]?#[ \t]*if(?P<df>ndef)?[ \t]*(?(df)|(!defined))[ \t]*\(? ?(\w+)\)?(.*)")),
(True, re.compile("^[ \t]?#[ \t]*(if)[ \t]*(([\(\)\w]+))"))
]

#list of elif expressions
elifA = [
(True, re.compile("^[ \t]?#[ \t]*elif[ \t]*defined\((.*)\)")),
(False, re.compile("^[ \t]?#[ \t]*elif[ \t]*!defined\((.*)\)")),
]

elsesearch = re.compile("^[ \t]?#[ \t]*else.*")
endifsearch = re.compile("^[ \t]?#[ \t]*endif.*")

FoldRegKey = "FoldRegion"

class FoldSetRegionCommand( sublime_plugin.TextCommand ) :
  '''Set region for fold to work within.
      If selection empty the region will be cleared.'''

  def run( self, edit ) :
    vw = self.view
    s = vw.sel()[0]
    if s.empty() :
      vw.erase_regions(FoldRegKey)
    else:
      vw.add_regions(FoldRegKey, [s], scope = "blue", flags = sublime.DRAW_NO_FILL)

class DefineCommand( sublime_plugin.TextCommand ) :
  '''Grab word under selections do the desired action on the def list.'''
  def run( self, edit, cmd = "toggle" ) :
    vw = self.view
#    dbgprint("running")
    if cmd == 'add' :       #Make sure word is in the define list.
      runcmd = AddWord
    elif cmd == 'toggle' :  #If word in list remove else add.
      runcmd = ToggleWord
    else:                   #make sure word is not in define list.
      runcmd = RemoveWord

    change = False

    for s in vw.sel() :
      #Get word under selection and add to list.
      word = vw.word(s.a)
      wordstr = vw.substr(word)
      change |= runcmd(wordstr)

    #Redo the fold conditions.
    if change :
      vw.run_command("fold_conditions")

class DefineRemoveSelCommand( sublime_plugin.TextCommand ) :
  '''Show list of defined words and remove picked word.'''
  def run( self, edit ) :
    if len(Defines) :
      self.view.window().show_quick_panel(Defines, self.ondone)

  def ondone( self, aArg ) :
    if aArg != -1 :
      Defines.remove(Defines[aArg])
      self.view.run_command("fold_conditions")

def CheckMore( aValue, aLine ) :
  '''Check to see if more expressions exist on the line.'''
  if aLine == "" :
    return aValue

#  dbgprint("Checking more " + aLine)
  for srch in moredefA :
    res = srch[1].search(aLine)
    if res and res.lastindex :
#      dbgprint("Matched {} checkmore {}".format(res.group(1), res.lastindex))
      defd = srch[0] if Defined(res.group(1)) else not srch[0]
      if res.lastindex == 2 :
        CheckMore(defd, res.group(2))
      aValue = srch[2](aValue, defd)

  return aValue

nsState, nsRange, nsEval, nsSibling, nsChildren = range(5)
NodeStack = None #Stack of (state, Range, Eval, Sibling, Children)
view = None

def PushChild( aState, aRange, aEval ) :
  '''Push data onto the child list of the top state in the stack'''
  global NodeStack
  node = (aState, aRange, aEval, [], [])
  NodeStack[0][nsChildren].insert(0, node)
  NodeStack.insert(0, node)

def Pop( ) :
  '''Pop state from the top of the stack.'''
  global NodeStack
  if len(NodeStack) > 1 :
    NodeStack.pop(0)
    return True
  return False

def PushSibling( aState, aRange, aEval, aPush = True ) :
  '''Push data onto the sibling list of the top state in the stack'''
  global NodeStack
  node = (aState, aRange, aEval, [], [])
  NodeStack[0][nsSibling].insert(0, node)
  res = Pop()
  if (aPush):
    NodeStack.insert(0, node)
  return res

def EvalFree( aRange, aHidden ) :
  '''Evaluation function for open state (not in a condition yet)'''
#  dbgprint("open")
  return 0

def EvalIf( OnOff, aRes, aRange, aHidden ) :
  '''Evaluation function for an if expression.'''
#  dbgprint(aRes.groups())
#  row, _ = view.rowcol(aRange.a)
#  dbgprint(row)
  defd = OnOff if Defined(aRes.group(3)) else not OnOff
#  dbgprint("{} last index {}".format(res.group(1), res.lastindex))
  if aRes.lastindex == 4 :
    defd = CheckMore(defd, aRes.group(4))
#  dbgprint(aRange, aRes.group(0), defd)
  return int(not defd)

def EvalElIf( OnOff, aRes, aRange, aHidden ) :
  '''Evaluation function for an elif expression.'''
  res = (aHidden ^ 1) << 1
  if not res:
    defd = OnOff if Defined(aRes.group(1)) else not OnOff
    res = int(not defd)
#  dbgprint(aRange, aRes.group(0), res)
  return res

def EvalElse( aRange, aHidden ) :
  '''Evaluation function for an else expression.'''
  ln = view.line(aRange)
  line = view.substr(ln)
#  dbgprint(aRange, line, aHidden)
  return aHidden ^ 1

def EvalEndIf( aRange, aHidden ) :
  '''Evaluation function for an endif expression.'''
  aHidden = 0
  ln = view.line(aRange)
  line = view.substr(ln)
#  dbgprint(aRange, line, aHidden)
  return aHidden

def IfDef( aRange, aLine ) :
  '''Determine if line is an #if expression.'''
  for srch in ifdefA :
    res = srch[1].search(aLine)
    if res and res.lastindex :
#      dbgprint("Define:", aLine)
      PushChild(ifstate, aRange, functools.partial(EvalIf, srch[0], res))
      return True
  return False

def ElIf( aRange, aLine ) :
  '''Determine if line is an #elif expression.'''
  for srch in elifA :
    res =  srch[1].search(aLine)
    if res :
      return PushSibling(ifstate, aRange, functools.partial(EvalElIf, srch[0], res))
    return False

def Else( aRange, aLine ) :
  '''Determine if line is an #else expression.'''
  res = elsesearch.search(aLine)
  if res != None :
    return PushSibling(elsestate, aRange, EvalElse)
  return False

def EndIf( aRange, aLine ) :
  '''Determine if line is an #endif expression.'''
  res = endifsearch.search(aLine)
  if res != None :
#    dbgprint("Endif:", aLine)
    return PushSibling(freestate, aRange, EvalEndIf, False)
  return False

def freestate( aRange, aLine ) :
  '''Process a line while in a free (non-condition) state.'''
  res = None
  if not IfDef(aRange, aLine) :
    if (Else(aRange, aLine)) or (ElIf(aRange, aLine)) or (EndIf(aRange, aLine)):
      res = "Unmatched condition"
  return res

def ifstate( aRange, aLine ) :
  '''Process a line while in an if condition.'''
  if not IfDef(aRange, aLine):
    if (not Else(aRange, aLine)) and (not ElIf(aRange, aLine)):
      EndIf(aRange, aLine)
  return None

def elsestate( aRange, aLine ) :
  '''Process a line while in an else condition.  Else conditions are not allowed now.'''
  if not IfDef(aRange, aLine):
      if not ElIf(aRange, aLine):
        if not EndIf(aRange, aLine):
          if Else(aRange, aLine):
            return "Nested Else"
  return None

def PatchEndifs( aView, aDest ) :
  '''Some #endifs are not correctly tagged so we have to search for
      them manually and add them to the list.'''
  ees = aView.find_all(endifsearch.pattern)
  for ee in ees:
    score = aView.score_selector(ee.begin(), 'meta.preprocessor.c')
    if not score :
      aDest.append(ee)

def FillNodeStack( aView ) :
  global NodeStack
  global view

  view = aView

  #Start in a free state with no region.
  NodeStack = [(freestate, None, EvalFree, [], [])] #Stack of state, Region, Eval, Sibling, Children

  #Find #ifdef, #endif.
  conditionRegs = aView.find_by_selector("preprocessor.keyword.control.import.c")
  #Find #else, #elif
  conditionRegs = conditionRegs + aView.find_by_selector("preprocessor.import.control.keyword.c")
  #Find #if
  conditionRegs = conditionRegs + aView.find_by_selector("preprocessor.keyword.control.import.if.c")
  #Find #else matched with #if.
  conditionRegs = conditionRegs + aView.find_by_selector("preprocessor.keyword.control.import.else.c")
  #Make sure no untagged endifs are left out.
  PatchEndifs(aView, conditionRegs)

  #Sort all the entries by location.
  conditionRegs = sorted(conditionRegs, key = lambda r: r.begin())

  ss = aView.get_regions(FoldRegKey)
  if len(ss) :
    s = ss[0]
    if not s.empty() :
      conditionRegs = [ x for x in conditionRegs if x.intersects(s) ]

  for r in conditionRegs:
    ln = aView.line(r)
    line = aView.substr(ln)
#    dbgprint(aView.rowcol(ln.begin()), line)
    #Run the line through the top state on the stack.
    err = NodeStack[0][nsState](ln, line)
    #if err is set then we ran into an error so show it to the user.
    if err :
      row, _ = aView.rowcol(ln.begin())
      msg = "{} line {} - {}".format(err, row + 1, line)
      print(msg)
      aView.show_at_center(ln)
      aView.sel().clear()
      aView.sel().add(ln)
      sublime.error_message(msg)
      break

  if len(NodeStack) > 1 :
    for s in NodeStack[:-1] :
      ln = aView.line(s[nsRange])
      row, _ = aView.rowcol(ln.begin())
      line = aView.substr(ln)
      print("Unclosed condition", row + 1, line)
    return False

  return True

class FoldConditionsCommand( sublime_plugin.TextCommand ) :
  def __init__( self, edit ) :
    super(FoldConditionsCommand, self).__init__(edit)
    self.reset()

  def StopFolding( self, aRegion ) :
    '''Add a fold region and go into an expanded state.'''
    r = sublime.Region(self.startPoint, max(aRegion.begin() - 1, 0))
    self.fold.append(r)
#    dbgprint("fold", r)
    self.startPoint = aRegion.end() + 1
    self.Folding = False

  def StartFolding( self, aRegion ) :
    '''Stop expanded state and start a folding region.'''
#    dbgprint("expand", aRegion)
    self.startPoint = aRegion.end() + 1
    self.Folding = True

  def crawl( self, aState, aHidden ) :
    '''Recursively run through the state trees and process the regions.'''

    #run the state evaluation function with the region and current Hidden state.
    aHidden = aState[nsEval](aState[nsRange], aHidden)
#    dbgprint(aHidden)

    #if the state is active then run the children
    if not aHidden :
      #If folding stop it as we are now in an open state.
      if self.Folding :
        self.StopFolding(aState[nsRange])

      #process the children because they will be visible.
      for child in aState[nsChildren]:
        self.crawl(child, aHidden)
    else:
      #if not folding start folding.
      if not self.Folding:
        self.StartFolding(aState[nsRange])

    #Process the siblings.
    for sibling in aState[nsSibling]:
      aHidden = self.crawl(sibling, aHidden)

  def reset( self ) :
    global NodeStack
    global view
    self.startPoint = 0
    self.fold = [ ]
    self.Folding = False
    NodeStack = None
    view = None

  def run( self, edit ) :

    self.view.run_command("unfold_all")

    if FillNodeStack(self.view) :
      self.crawl(NodeStack[0], 0)
      self.view.fold(self.fold)

    self.reset()

class MatchingConditionCommand( sublime_plugin.TextCommand ) :
  def __init__( self, edit ) :
    super(MatchingConditionCommand, self).__init__(edit)
    self.reset()

  def reset( self ) :
    global NodeStack
    global view
    NodeStack = None
    view = None
    self.MyLine = None

  def findother( self, aNodes ) :
    for node in aNodes :
      while node :
        prevNode = node
        node = prevNode[nsSibling][0] if len(prevNode[nsSibling]) else None
        if node :
#          ln = self.view.line(prevNode[1])
#          line = self.view.substr(ln)
#          ln2 = self.view.line(node[1])
#          line2 = self.view.substr(ln2)
#          dbgprint("looking", line, line2)

          if prevNode[nsRange].a == self.MyLine.a :
            return node
          elif node[nsRange].a == self.MyLine.a :
            return prevNode

          r = prevNode[nsRange].cover(node[nsRange])
          if r.contains(self.MyLine.a) :
            return self.findother(prevNode[nsChildren])

    return None

  def run( self, edit ) :
    vw = self.view

    #todo: Check current line for correct type.
    s = vw.sel()[0]
    ln = vw.line(s)
    #note: This will match pragmas as well but I don't worry about that.
    c1 = "preprocessor.keyword.control.import.if.c"
    c2 = "preprocessor.import.control.keyword.c"
    score = vw.score_selector(ln.begin(), c1)
    score |= vw.score_selector(ln.begin(), c2)
    #If beginning of line doesn't match score try cursor position.
    if not score :
      score = vw.score_selector(s.a, c1)
      score |= vw.score_selector(s.a, c2)

#    line = vw.substr(ln)
#    dbgprint(line, "is", score)

    if score :
      if FillNodeStack(vw) :
        self.MyLine = ln
        res = self.findother(NodeStack[0][nsChildren])
        if res :
          p = res[nsRange].a
          vw.show_at_center(p)
          vw.sel().clear()
          vw.sel().add(sublime.Region(p, p))

      self.reset()


