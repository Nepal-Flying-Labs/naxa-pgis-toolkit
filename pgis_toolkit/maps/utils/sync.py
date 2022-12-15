from config.settings.base import MONGO_DB, env
from pgis_toolkit.maps.models import FeatureCollection


def sync_featurecollection():
    feature_qs = FeatureCollection.active.all().values('id', 'layer', 'sub_layer', 'attributes')
    feature_coll = MONGO_DB['featurecollections']
    if feature_qs:
        for feature in feature_qs:
            feature_count = feature_coll.count_documents({'id':feature['id']})
            if feature_count == 0:
                feature_coll.insert_one(feature)
                print('feature added:', feature['id'])
            else:
                feature_coll.update_one({'id': feature['id']}, {'$set': feature})
                print('feature updated:', feature['id'])
    print('Completed')
