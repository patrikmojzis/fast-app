class QueryBuilder:
    def __init__(self, model_class, query=None):
        self.model_class = model_class
        self.query = query or {}
        self.sort_options = None
        self.limit_value = None
        self.skip_value = None
        self._pending_coroutines = []

    async def __build_kwargs(self):
        """Build kwargs for the query"""
        kwargs = {}
        if self.sort_options is not None:
            kwargs['sort'] = self.sort_options
        if self.limit_value is not None:
            kwargs['limit'] = self.limit_value
        if self.skip_value is not None:
            kwargs['skip'] = int(self.skip_value)
        return kwargs
    
    async def find(self):
        """Execute the query and return results"""
        await self._apply_pending_coroutines()
        
        return await self.model_class.find(self.query, **(await self.__build_kwargs()))

    async def find_one(self):
        """Execute the query and return a single result"""
        # Apply any pending coroutines
        await self._apply_pending_coroutines()
        
        return await self.model_class.find_one(self.query, **(await self.__build_kwargs()))
        
    async def count(self):
        """Count matching documents"""
        # Apply any pending coroutines
        await self._apply_pending_coroutines()
        
        return await self.model_class.count(self.query)
        
    def limit(self, value):
        """Set limit"""
        self.limit_value = value
        return self
        
    def skip(self, value):
        """Set skip"""
        self.skip_value = value
        return self
        
    def sort(self, *args):
        """Set sort options"""
        self.sort_options = args
        return self
    
    async def _apply_pending_coroutines(self):
        """Apply any pending async scope results"""
        for coroutine in self._pending_coroutines:
            query_update = await coroutine
            self.query.update(query_update)
        self._pending_coroutines = []
    
    # This allows extending with custom scopes
    def __getattr__(self, name):
        if hasattr(self.model_class, f"scope_{name}"):
            scope_method = getattr(self.model_class, f"scope_{name}")
            
            def scope_wrapper(*args, **kwargs):
                # Run the scope method
                result = scope_method(self.query, *args, **kwargs)
                
                # If it's a coroutine, add to pending list
                if hasattr(result, "__await__"):
                    self._pending_coroutines.append(result)
                else:
                    # Handle synchronous scope directly
                    self.query = result
                
                return self
                
            return scope_wrapper
            
        raise AttributeError(f"No scope named '{name}' on {self.model_class.__name__}")