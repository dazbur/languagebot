# coding=utf8
import difflib

a = "страстно желать"
b = "1.Страстно желать"
 

s = difflib.SequenceMatcher(None, a, b)
print s.ratio() 