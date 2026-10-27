import re
p = 'muzika_app/views.py'
s = open(p, encoding='utf-8').read()
s = re.sub(r'(\{e\}"\))[^\S\n]+(else:)', lambda m: m.group(1) + '\n' + ' ' * (12 if 'x' else 0) + m.group(2), s, count=1)
s = re.sub(r'(\{e\}"\))[^\S\n]+(else:)', lambda m: m.group(1) + '\n        ' + m.group(2), s, count=1)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
