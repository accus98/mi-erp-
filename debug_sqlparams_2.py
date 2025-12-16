import sqlparams

print("Doc:", sqlparams.SQLParams.__doc__)
import inspect
print("Sig:", inspect.signature(sqlparams.SQLParams))

# Try qmark input
c1 = sqlparams.SQLParams('numeric_dollar', 'qmark')
print("Qmark Test:", c1.format("SELECT * FROM t WHERE id=?", [123]))

# Try explicit format input again
c2 = sqlparams.SQLParams('numeric_dollar', 'format')
print("Format Test:", c2.format("SELECT * FROM t WHERE id=%s", [123]))

# Try pyformat
c3 = sqlparams.SQLParams('numeric_dollar', 'pyformat')
print("Pyformat Test:", c3.format("SELECT * FROM t WHERE id=%s", [123]))
