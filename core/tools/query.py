try:
    from pypika import Query, Table, Field, Order
    from pypika.terms import Parameter
except ImportError:
    print("CRITICAL: pypika not installed. Please install pypika.")
    Query = object
    Table = object

class QueryBuilder:
    """
    Safe SQL Query Builder using Pypika.
    Wraps Pypika to integrate with our Native SQL ($n) logic.
    """
    
    def __init__(self, table_name):
        self.table = Table(table_name)
        self.query = Query.from_(self.table)
        
    def select(self, *fields):
        if not fields:
            self.query = self.query.select('*')
        else:
            # Handle list of fields
            cols = []
            for f in fields:
                if f == '*':
                    cols.append('*')
                else:
                    cols.append(self.table[f])
            self.query = self.query.select(*cols)
        return self

    def where(self, domain, sql_params_converter):
        """
        Applies domain to query using sql_params_converter to generate $n params.
        But Pypika handles params too?
        Pypika uses Parameters.
        If we use Pypika, we should let Pypika generate the SQL string with placeholders.
        But asyncpg needs $1, $2.
        Pypika supports Parameter('$1')?
        NO. Pypika generates named params or %s usually.
        
        Hybrid Approach:
        Use Pypika for structure (SELECT "col" FROM "table").
        Use manual WHERE clause construction via DomainParser because our Domain logic is complex (Polish notation).
        
        So:
        q = QueryBuilder('res_partner').select('id', 'name')
        sql = q.get_sql() 
        # sql -> SELECT "id", "name" FROM "res_partner"
        
        Then append WHERE clause manually?
        query = f"{sql} WHERE {where_clause}"
        
        This avoids manually building the SELECT/FROM part which is risky for injection if table name is unchecked.
        (Though table name comes from class attribute _table, so widely safe).
        
        The Audit found risk in `create`:
        columns = ", ".join(f'"{k}"' for k in vals.keys())
        
        We can use Pypika for INSERT too.
        """
        pass
        
    def get_sql(self):
        return self.query.get_sql(quote_char='"')

    @staticmethod
    def build_insert(table_name, columns):
        """
        Returns (query_str, placeholder_str)
        INSERT INTO "table" ("col1", "col2") VALUES ($1, $2)
        """
        t = Table(table_name)
        q = Query.into(t).columns(*columns)
        # Values? We usually do bulk insert or runtime values.
        # Pypika insert wants values.
        # q.insert(Parameter('$1'), Parameter('$2'))
        return q
