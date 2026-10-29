import pathlib
p = pathlib.Path("replay.py")
s = p.read_text(encoding="utf-8")
s = s.replace('r\\"\\"\\"', 'r"""')
s = s.replace('\\"\\"\\"', '"""')
p.write_text(s, encoding="utf-8")
print("fixed replay.py quote escaping")
