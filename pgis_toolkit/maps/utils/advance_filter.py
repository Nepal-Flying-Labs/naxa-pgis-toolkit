
'''function to filer dataset'''
def advance_filter_data(field, operator, value, dataset):
    result_dataset = []
    if operator == 1:
        key = "attributes__"+field
    elif operator == 2:
        key = "attributes__"+field+"__lt"
    elif operator == 3:
        key = "attributes__"+field+"__gt"
    elif operator == 4:
        key = "attributes__"+field
    elif operator == 5:
        key = "attributes__"+field+"__lte"
    elif operator == 6:
        key = "attributes__"+field+"__gte"
    elif operator == 7:
        if "%" in value:
            if value.startswith("%") and value.endswith("%"):
                value = value.strip("%")
                key = "attributes__"+field+"__icontains"
            elif value.startswith("%"):
                value = value.strip("%")
                key = "attributes__"+field+"__endswith"
            elif value.endswith("%"):
                value = value.strip("%")
                key = "attributes__"+field+"__startswith"
            elif not value.startswith("%") and not value.endswith("%"):
                value = value.split("%")
                key1 = "attributes__"+field+"__startswith"
                key2 = "attributes__"+field+"__endswith"
                filter_dict = {}
                filter_dict[key1] = value[0]
                filter_dict[key2] = value[1]
                result_dataset = dataset.filter(**filter_dict)
                return result_dataset
    filter_dict = {}
    filter_dict[key] = value
    result_dataset = dataset.filter(**filter_dict)
    return result_dataset
