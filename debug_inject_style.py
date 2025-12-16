import sqlparams
import sqlparams._styles as styles

print("Existing keys:", list(styles.STYLES.keys()))
fmt = styles.STYLES['numeric']
print("Numeric style object:", fmt)
print("Numeric type:", type(fmt))
print("Numeric attributes:", dir(fmt))

# Try to see signature
try:
    # It might be a tuple or a namedtuple or class
    print("Numeric check:", fmt[0], fmt[1]) 
except:
    pass
