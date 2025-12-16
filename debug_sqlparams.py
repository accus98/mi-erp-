import sqlparams
try:
    print("Styles:", sqlparams.STYLES) # If exposed
except:
    pass

try:
    # Try common ones
    s = sqlparams.SQLParams('numeric', 'format')
    print("Numeric check:", s.format('SELECT %s', [1]))
except Exception as e:
    print("Numeric failed:", e)

try:
    # Try to see if there is a 'postgresql' or similar
    import inspect
    print(dir(sqlparams))
except:
    pass
