class SerializeContext:
    ''' Helps with serializing stuff. '''

    def __init__(self):

        # Used for generating IDs.
        self.id_counter = 0

        # ID to context-specific value.
        self.id_to_value = {}

        # Context-specific value to id.
        self.value_to_id = {}

    def new_id(self, obj) -> int:
        ''' Generate a new ID that can be used to create a persistent reference
            to the given object. 
            
            If the object already was assigned an id, that ID will be returned
            even if it doesn't use the same prefix rule.
        '''

        if obj in self.value_to_id:
            return self.value_to_id[obj]

        id = self.id_counter
        self.id_counter += 1
        self.value_to_id[obj] = id
        return id

    def new_str_id(self, obj, prefix) -> str:
        ''' Generate a new ID that can be used to create a persistent reference
            to the given object. 
            
            If the object already was assigned an id, that ID will be returned
            even if it doesn't use the same prefix rule.
        '''

        if obj in self.value_to_id:
            return self.value_to_id[obj]

        id = f"{prefix}{self.id_counter}"
        self.id_counter += 1
        self.value_to_id[obj] = id
        return id

    def new_static_id(self, obj, id) -> str:
        ''' Similar to the other new_id variants but just takes the given id,
            uses it and returns it without modification. '''

        if obj in self.value_to_id:
            return self.value_to_id[obj]

        self.value_to_id[obj] = id
        return id
