
from lsst.sims.maf.driver.mafConfig import configureSlicer, configureMetric, makeDict
import os
import numpy as np

dbDir = '.'
runName = 'ops1_1140'
sqlitefile = os.path.join(dbDir, runName + '_sqlite.db')
root.dbAddress ={'dbAddress':'sqlite:///'+sqlitefile}
root.opsimName = runName
root.outputDir = 'GapsDir'


slicerList = []
nside = 128
band='r'
slicerList = []


# Let's do a really high res with the chip gaps on!

nside = 2048/2

m1 = configureMetric('CountMetric', kwargs={'col':'expMJD'})
slicer = configureSlicer('HealpixSlicer',
                       kwargs={'nside':nside, 'spatialkey1':'fieldRA', 'spatialkey2':'fieldDec',
                               'useCamera':True},
                       metricDict=makeDict(*[m1]),
                       constraints=['filter="%s" and  fieldRA > 0 and fieldRA < %f and  fieldDec < 0 and fieldDec > %f'%
                                    (band, np.radians(10), np.radians(-10))])
slicerList.append(slicer)


root.slicers=makeDict(*slicerList)
