from config.settings.base import MONGO_DB, env
from pgis_toolkit.maps.models import FeatureCollection, FeatureCollectionMirror


def sync_featurecollection(layer):
    if layer=='all':
        feature_qs = FeatureCollection.active.all().values('id', 'layer', 'sub_layer', 'attributes')
    else:
        feature_qs = FeatureCollection.active.filter(layer=layer).values('id', 'layer', 'sub_layer', 'attributes')
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

def sync_featurecollection_mirror(layer):
    if layer=='all':
        feature_qs = FeatureCollectionMirror.active.all().values('id', 'feature', 'layer', 'sub_layer', 'attributes')
    else:
        feature_qs = FeatureCollectionMirror.active.filter(layer=layer).values('id', 'feature', 'layer', 'sub_layer', 'attributes')
    feature_coll = MONGO_DB['featurecollectionsmirror']
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
