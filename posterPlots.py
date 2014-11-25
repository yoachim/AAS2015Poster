# Make plots for AAS poster

from lsst.sims.maf.driver.mafConfig import configureSlicer, configureMetric, makeDict
import os


dbDir = '.'
runName = 'ops1_1140'
sqlitefile = os.path.join(dbDir, runName + '_sqlite.db')
root.dbAddress ={'dbAddress':'sqlite:///'+sqlitefile}
root.opsimName = runName
root.outputDir = 'OutDir'


slicerList = []
nside = 128
band='r'
slicerList = []


m1 = configureMetric('Coaddm5Metric',
                     plotDict={'title':'Co-added Depth', 'colorMin':25, 'colorMax':28})
slicer=configureSlicer('HealpixSlicer',
                       kwargs={'nside':nside, 'spatialkey1':'fieldRA', 'spatialkey2':'fieldDec'},
                       metricDict=makeDict(*[m1]),
                       constraints=['filter="%s"'%band])
slicerList.append(slicer)

m1 = configureMetric('Coaddm5Metric',
                     plotDict={'title':'Dithered Co-added Depth', 'colorMin':25, 'colorMax':28})
slicer=configureSlicer('HealpixSlicer',
                       kwargs={'nside':nside, 'spatialkey1':'ditheredRA', 'spatialkey2':'ditheredDec'},
                       metricDict=makeDict(*[m1]),
                       constraints=['filter="%s"'%band], metadata='dithered')
slicerList.append(slicer)


root.slicers=makeDict(*slicerList)
