from option_component import load_option_component

component_name_to_load_fn = {
    'option': load_option_component
}


def load_components_from_dict(p, asset, data_dict, key_name):
    ''' Load a list of asset plugin components from a data dictionary. '''

    if data_dict is None:
        return []
    
    raw_list = data_dict[key_name]
    for raw_component in raw_list:
        fn = component_name_to_load_fn(raw_component['componentName'])
        return fn(p, asset, data_dict)