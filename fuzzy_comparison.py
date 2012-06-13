# coding=utf8
import difflib

a = "жестоко,яростно, свирепо, дико, неистово. Ужасно, невыносимо"
b = "ужасно, невыносимо, яростно, жестоко"
 

s = difflib.SequenceMatcher(None, a, b)
print s.ratio() 