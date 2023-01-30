from config.settings.base import MONGO_DB, env
from pgis_toolkit.maps.models import FeatureCollection, FeatureCollectionMirror


def sync_featurecollection(layer):
    if layer=='all':
        feature_qs = FeatureCollection.active.all().values('id', 'layer', 'sub_layer', 'attributes')
    else:
        feature_qs = FeatureCollection.active.filter(layer=layer).values('id', 'layer', 'sub_layer', 'attributes')
    if feature_qs:
        feature_coll = MONGO_DB['featurecollections']
        for feature in feature_qs:
            feature_coll.update_one({'id': feature['id']}, {'$set': feature}, upsert=True)
            print('feature updated:', feature['id'])
    print('Completed')

def sync_featurecollection_mirror(layer):
    if layer=='all':
        feature_qs = FeatureCollectionMirror.active.all().values('id', 'feature', 'layer', 'sub_layer', 'attributes')
    else:
        feature_qs = FeatureCollectionMirror.active.filter(layer=layer).values('id', 'feature', 'layer', 'sub_layer', 'attributes')
    if feature_qs:
        feature_coll = MONGO_DB['featurecollectionsmirror']
        for feature in feature_qs:
            feature_coll.update_one({'id': feature['id']}, {'$set': feature}, upsert=True)
            print('feature updated:', feature['id'])
    print('Completed')
