class SQLParams:
    """
    Helper to build SQL query with incremental $n placeholders.
    """
    def __init__(self, start_index=1):
        self.params = []
        self.index = start_index

    def add(self, value):
        """
        Add a single value and return the placeholder string ($n).
        """
        self.params.append(value)
        p = f"${self.index}"
        self.index += 1
        return p

    def add_many(self, values):
        """
        Add multiple values and return placeholder comma-separated string ($n, $n+1...).
        """
        placeholders = []
        for v in values:
            placeholders.append(self.add(v))
        return ", ".join(placeholders)

    def get_params(self):
        return tuple(self.params)
