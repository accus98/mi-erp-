import sqlparams

# Verify CORRECT order: in='format' (%s), out='numeric_dollar' ($n)
converter = sqlparams.SQLParams('format', 'numeric_dollar')

query = 'SELECT * FROM t WHERE id=%s'
args = [123]

pg_query, new_args = converter.format(query, args)
print(f"Query: {pg_query}")
print(f"Args: {new_args}")
