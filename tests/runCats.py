import scipy
from lsst.sims.catalogs.generation.db import\
        DBObject, ObservationMetaData
from lsst.sims.catalogs.measures.example_utils.exampleCatalogDefinitions import\
        RefCatalogGalaxyBase
class RefCatalogGalaxyTiled(RefCatalogGalaxyBase):
    catalog_type = 'ref_catalog_galaxy_tiled'
    refIdCol = 'galtileid'

if __name__ == '__main__':
    obsMD = DBObject.from_objid('opsim3_61')
    obs_metadata = obsMD.getObservationMetaData(88544919, 0.1, makeCircBounds=True)
    obs_metadata_gal = ObservationMetaData(circ_bounds=dict(ra=.0,
                                                        dec=.0,
                                                        radius=0.1))
    objectDict = {}
    objectDict['testStars'] = {'dbobj':DBObject.from_objid('msstars'),
                               'constraint':None,
                               'filetype':'trim_catalog_POINT',
                               'obsMetadata':obs_metadata}
    objectDict['testGalaxyBase'] = {'dbobj':DBObject.from_objid('galaxyBase'),
                               'constraint':"r_ab < 22",
                               'filetype':'ref_catalog_galaxy',
                               'obsMetadata':obs_metadata_gal}
    objectDict['testTiledGalaxy'] = {'dbobj':DBObject.from_objid('galaxyTiled'),
                               'constraint':"r_ab < 20",
                               'filetype':'ref_catalog_galaxy_tiled',
                               'obsMetadata':obs_metadata}
    objectDict['testGalaxyBulge'] = {'dbobj':DBObject.from_objid('galaxyBulge'),
                               'constraint':"mass_bulge > 1. and sedname_bulge is not NULL",
                               'filetype':'trim_catalog_SERSIC2D',
                               'obsMetadata':obs_metadata}
    objectDict['testGalaxyDisk'] = {'dbobj':DBObject.from_objid('galaxyDisk'),
                               'constraint':"DiskLSSTg < 20. and sedname_disk is not NULL",
                               'filetype':'trim_catalog_SERSIC2D',
                               'obsMetadata':obs_metadata}
    objectDict['testGalaxyAgn'] = {'dbobj':DBObject.from_objid('galaxyAgn'),
                               'constraint':"sedname_agn is not NULL",
                               'filetype':'trim_catalog_ZPOINT',
                               'obsMetadata':obs_metadata}

    for objKey in objectDict.keys():
        dbobj = objectDict[objKey]['dbobj']
        t = dbobj.getCatalog(objectDict[objKey]['filetype'],
                             obs_metadata=objectDict[objKey]['obsMetadata'], 
                             constraint=objectDict[objKey]['constraint'])

        print
        print "These are the required columns from the database:"
        print t.db_required_columns()
        print
        print "These are the columns that will be output to the file:"
        print t.column_outputs
        print
    
        filename = 'catalog_test_%s.dat'%(dbobj.objid)
        print "querying and writing catalog to %s:" % filename
        t.write_catalog(filename)
        filename = 'catalog_test_%s_chunked.dat'%(dbobj.objid)
        t.write_catalog(filename, chunk_size=10)
        print " - finished"