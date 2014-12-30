
# coding: utf-8

## Time Delay Accuracy Metric and MAF Python script

# This ipython notebook is intended to provide documentation of two things: Phil Marshall's time delay accuracy metrics and an example of writing a python script to interact with the innards of MAF (rather than working with the driver and driver configuration file).
#
# Why would you skip the driver? In this case, Phil has a metric that returns several values per slicePoint (a 'complex' metric).  This is because the metric is calculating several different values that all depend on the same underlying (slightly expensive to calculate) quantities -- these values (Accuracy A, Precision P, and success rate f) are documented in http://arxiv.org/pdf/1409.1254.pdf (Liao et al).  These values are calculated as follows:

# \begin{align}
# |A|_{\rm model} &\approx 0.06\% \left(\frac{\rm cad} {\rm 3 days}  \right)^{0.0}
#                           \left(\frac{\rm sea}  {\rm 4 months}\right)^{-1.0}
#                           \left(\frac{\rm camp}{\rm 5 years} \right)^{-1.1} \notag \\
#   P_{\rm model} &\approx 4.0\% \left(\frac{\rm cad} {\rm 3 days}  \right)^{ 0.7}
#                          \left(\frac{\rm sea}  {\rm 4 months}\right)^{-0.3}
#                          \left(\frac{\rm camp}{\rm 5 years} \right)^{-0.6} \notag \\
#   f_{\rm model} &\approx 30\% \left(\frac{\rm cad} {\rm 3 days}  \right)^{-0.4}
#                         \left(\frac{\rm sea}  {\rm 4 months}\right)^{ 0.8}
#                         \left(\frac{\rm camp}{\rm 5 years} \right)^{-0.2} \notag
# \end{align}

# So we want to skip the driver because we want to be able to control the plotting parameters for A, P, and f with more specificity than is currently allowed by the driver configuration files (this will change in the future, but is a problem for now), if these are just calculated as 'reduce' functions on a single metric.

### Python Script

# The python for Phil's new metric class is in sims_maf_contrib/mafContrib (https://github.com/LSST-nonproject/sims_maf_contrib/tree/master/mafContrib/tdcMetric.py)

# To use his new metric, we're going to write some re-usable functions to interact with various levels of MAF and call these as we go along with this particular example.

# First we import the modules we'll need, including the module with the contributed metrics and stackers, 'mafContrib'.

# In[1]:

import os
import glob
# Import MAF modules.
import lsst.sims.maf.db as db
import lsst.sims.maf.slicers as slicers
import lsst.sims.maf.metrics as metrics
import lsst.sims.maf.stackers as stackers
import lsst.sims.maf.sliceMetrics as sliceMetrics
# Import the contributed metrics and stackers (note this will add their info to the Metric and Stacker registry)
import mafContrib
# Import a MAF utility to identify the sources of columns (database or stackers)
# Note we have to import this last, as it executes code that operates on the stacker registry (including contributed stackers).
from lsst.sims.maf.utils import ColInfo


# Identify database information for this example.

# In[2]:

opsimName = 'ops2_1075'
dbAddress = 'sqlite:///' + opsimName + '_sqlite.db'
outputDir = 'Output'


# Next let's write a function to instantiate the metric(s) and slicer we want to use. We will call this function first (before reading the data from the database) because by instantiating these objects first, this sets up registries in MAF that track what columns need to be called from the database and what need to be calculated from stackers (and which stackers). Identifying these is done using the 'ColInfo' utility. ColInfo assumes any column not identified as being built by a stacker (via the stacker's 'colsAdded' value) comes directly from the database.
#
# Note we have not specified a sqlconstraint here. In this case, we're just running the same metrics and same slicer for all sqlconstraints.

# In[3]:

def getMetricsAndHealpixSlicer(raCol='ditheredRA', decCol='ditheredDec', nside=128):
    """
    Instantiate the metrics, healpix slicer, and stackers and identify the columns needed from the database for each of these.

    - raCol is the RA column to use for the slicer (can be a stacker column)
    - decCol is the dec column to use for the slicer (can be a stacker column)
    - nside is the resolution for the healpix slicer
    """
    # Instantiate the metrics.
    metrics = []
    metrics.append(mafContrib.TdcMetric(metricName='TDC', seasonCol='season', expMJDCol='expMJD', nightCol='night'))
    # Instantiate the slicer.
    slicer = slicers.HealpixSlicer(nside=nside, spatialkey1=raCol, spatialkey2=decCol)
    # Identify all of the columns we need from the database, using 'ColInfo' utility.
    # Also identify which stackers must be called (although we will allow override of these below)
    colInfo = ColInfo()
    # Save the columns direct from database
    dbcolnames = set()
    defaultstackers = set() # stacker names that must be called to create all necessary columns
    for col in raCol, decCol:
        colsource = colInfo.getDataSource(col)
        if colsource != colInfo.defaultDataSource:
            defaultstackers.add(colsource)
        else:
            dbcolnames.add(col)
    for col in metrics[0].colRegistry.colSet:
        colsource = colInfo.getDataSource(col)
        if colsource != colInfo.defaultDataSource:
            defaultstackers.add(colsource)
        else:
            dbcolnames.add(col)
    # If you want to specify options for stackers, do that here.
    stackers = []
    stackers.append(mafContrib.SeasonStacker())
    # Remove explicity instantiated stackers from defaultstacker set.
    for s in stackers:
        if s.__class__ in defaultstackers:
            defaultstackers.remove(s.__class__)
    # Instantiate the remaining default stackers.
    for s in defaultstackers:
        stackers.append(s())
    # Add the columns needed from the database from the stackers.
    for s in stackers:
        for col in s.colsReq:
            dbcolnames.add(col)
    return metrics, slicer, stackers, dbcolnames


# In[4]:

# Instantiate metrics, slicer and stackers and get the column names to be queried from the database.
metrics, slicer, stackers, dbcolnames = getMetricsAndHealpixSlicer()


# Now we write a function to get the data from the database for this sqlconstraint. We'll also take this opportunity to actually run the stackers and generate the additional data columns that are calculated by these. That way we generate a coherent 'simData' for all the visits which match this sqlconstraint.

# In[5]:

def getData(dbAddress, sqlconstraint, dbcolnames, stackers):
    """
    Get data from the database.

    - dbAddress is a sqlalchemy connection string, such as 'sqlite:///ops2_1078_sqlite.db'
    - sqlconstraint is a sql constraint for this query
    - dbcolnames are the names of the column to query from the database.
    - stackers is the list of instantiated stacker objects.
    """
    oo = db.OpsimDatabase(dbAddress)
    simData = oo.fetchMetricData(dbcolnames, sqlconstraint)
    for s in stackers:
        simData = s.run(simData)
    return simData


# In[6]:

# Set sqlconstraint.  (none here, so multi-band analysis)
sqlconstraint = ''
# Get data.
simData = getData(dbAddress, sqlconstraint, dbcolnames, stackers)


# Next we want to write a function that will take the simData and use it to 'setup' the slicer. This is necessary because each slicer indexes the simData so that it can effectively identify the relevant visits in the opsim data for each "slice" in the slicer. For example, a healpix slicer creates a kd-tree ranging over the opsim visits so that at each healpixel point, the visits which overlap that point can be quickly identified and returned to the user.

# In[7]:

def setupSlicer(slicer, simData):
    """
    Set up indexing in the slicer.
    """
    slicer.setupSlicer(simData)
    return slicer


# In[8]:

slicer = setupSlicer(slicer, simData)


# At this point, our data has been retrieved from the database, the slicer is ready to slice, and the thing that is left to do is actually calculate the metric values at each point in the slicer. We use the RunSliceMetric class from MAF to do this, as the sliceMetrics classes provides a higher-level interface uniting metrics and slicers. The RunSliceMetric gives users some easy ways to calculate metric values, run the reduce functions, create plots, and write metric data to disk. Here we'll write a function to go through the calculation and saving of the metric values, then will separate plotting into its own function (as Phil needs to customize the plotting).
#
# The option 'useResultsDb' means that the outputs of MAF will be registered in the results database (see the MAF documentation for more info, but this is necessary for the web interface visualization 'showMaf.py'). It could be safely turned off if the web interface view to the outputs isn't desired. The opsimName and metadata are used for automated output file name generation and plot titles as well as being stored to the output files as useful information to have later, and the sqlconstraint is just saved to the output file as useful information.

# In[9]:

def calculateMetrics(simData, slicer, metrics, opsimName, sqlconstraint, metadata=None, outputDir='Output', clobber=True):
    """
    Calculate metric values and reduced metric values.
    """
    # Add a more compact version of the sqlconstraint as the metadata if none provided.
    if metadata is None:
        metadata = sqlconstraint.replace("'",'').replace('"','').replace('  ', ' ')
        metadata = metadata.replace('filter', '').replace('=', '')
    if clobber:
        resultsdb = os.path.join(outputDir, 'resultsDb_sqlite.db')
        if os.path.isfile(resultsdb):
            os.remove(resultsdb)
    # Instantiate the RunSliceMetric.
    sm = sliceMetrics.RunSliceMetric(useResultsDb=True, outDir=outputDir)
    sm.setSlicer(slicer)
    sm.setMetrics(metrics)
    # Calculate the metric values.
    sm.runSlices(simData, simDataName=opsimName, sqlconstraint=sqlconstraint, metadata=metadata)
    # Calculate the 'reduced' metric values.
    sm.reduceAll()
    # Save the output files.
    sm.writeAll()
    return sm


# In[10]:

# Generate a 'nicer' version of the sqlconstraint for the metadata, and indicate this is being run on dithered RA/Dec.
metadata = sqlconstraint.replace('filter', '').replace('=', '')
metadata = metadata.replace('"', '').replace("'", '')
metadata += ' dithered'
sm = calculateMetrics(simData, slicer, metrics, opsimName, sqlconstraint, metadata, outputDir)


# Okay, now we generate the plots. We can re-run this function to set different plotting parameters and play with the plots.

# In[11]:

def plotMetrics(sm, metadata=None, order=0):
    """
    Generate the plots for Phil's metrics.
    """
    metricName = 'TDC_Accuracy'
    iid = sm.findIids(metricName=metricName, metadata=metadata)[0]
    # Set the plotting parameters for this value.
    minVal = 0.01
    maxAccuracy = 0.03
    sm.plotDicts[iid].update({'xMin':minVal, 'xMax':maxAccuracy, 'colorMin':minVal, 'colorMax':maxAccuracy,
                              'cbarFormat':'%.3f'})
    sm.displayDicts[iid].update({'group':'Time Delay Challenge',
                                 'order':order, 'caption':'Time Delay Challenge Accuracy plots. Smaller is better.'})
    sm.plotMetric(iid)

    metricName = 'TDC_Precision'
    iid = sm.findIids(metricName=metricName, metadata=metadata)[0]
    # Set the plotting parameters for this value.
    maxPrecision = 5.0
    sm.plotDicts[iid].update({'xMin':minVal, 'xMax':maxPrecision, 'colorMin':minVal, 'colorMax':maxPrecision})
    sm.displayDicts[iid].update({'group':'Time Delay Challenge',
                                 'order':order, 'caption':'Time Delay Challenge Precision plots. Smaller is better.'})
    sm.plotMetric(iid)

    metricName = 'TDC_Rate'
    iid = sm.findIids(metricName=metricName, metadata=metadata)[0]
    # Set the plotting parameters for this value.
    maxFrac = 40
    sm.plotDicts[iid].update({'xMin':minVal, 'xMax':maxFrac, 'colorMin':minVal,
                              'colorMax':maxFrac, 'cbarFormat':'%i'})
    sm.displayDicts[iid].update({'group':'Time Delay Challenge', 'order':order, 'caption':'Time Delay Challenge Fraction plots.'})
    # 'figs' is a dictionary of the figure names:fig numbers created when plotting this data.
    sm.plotMetric(iid)


# In[12]:

#get_ipython().magic(u'matplotlib inline')

fignums = plotMetrics(sm)


# Okay, those were reasonable plots. Let's go through all filters.

# Now we can put it together in a short script to run through multiple sqlconstraints.

# In[13]:

import matplotlib.pyplot as plt

opsimName = 'ops2_1075'
dbAddress = 'sqlite:///' + opsimName + '_sqlite.db'
outputDir = 'Output'

# Define our sqlconstraints.
sqlconstraints = []
for f in ('u', 'g', 'r', 'i', 'z', 'y', 'multi'):
    if f == 'multi':
        sqlconstraint = ''
    else:
        sqlconstraint = 'filter = "%s"' %(f)
    sqlconstraints.append(sqlconstraint)

# Instantiate the same slicer and metrics we'll use for all sqlconstraints.
metrics, slicer, stackers, dbcolnames = getMetricsAndHealpixSlicer(raCol='ditheredRA', decCol='ditheredDec', nside=128)

clobber = True
for i, sqlconstraint in enumerate(sqlconstraints):
    simData = getData(dbAddress, sqlconstraint, dbcolnames, stackers)
    if hasattr(slicer, 'opsimtree'):
        del slicer.opsimtree
    slicer = setupSlicer(slicer, simData)
    metadata = sqlconstraint.replace('filter', '').replace('=', '')
    metadata.lstrip(' ')
    if sqlconstraint == '':
        metadata = 'multi band'
    metadata += ' dithered'
    sm = calculateMetrics(simData, slicer, metrics, opsimName, sqlconstraint, metadata, outputDir, clobber=clobber)
    clobber = False
    plotMetrics(sm, metadata=metadata, order=i)
    plt.close('all')


# Hmm. Let's fiddle with plots and display parameters a bit more. We'll read the files back from disk (so we could come back to this later).

# In[14]:

metricdatafilesA = glob.glob(outputDir+'/*Accuracy*npz')#get_ipython().getoutput(u'ls $outputDir/*Accuracy*npz')
metricdatafilesP = glob.glob(outputDir+'/*Precision*npz')#get_ipython().getoutput(u'ls $outputDir/*Precision*npz')
metricdatafilesF = glob.glob(outputDir+'/*Rate*npz') #get_ipython().getoutput(u'ls $outputDir/*Rate*npz')
metricdatafiles = metricdatafilesA + metricdatafilesP + metricdatafilesF
print metricdatafiles


# In[15]:

sm = sliceMetrics.RunSliceMetric(useResultsDb=False)
sm.readMetricData(metricdatafiles)
sm.slicer = sm.slicers[0]


# In[16]:

for iid in sm.metricValues:
    print sm.metricNames[iid], sm.metadatas[iid]


# In[18]:

print sm.metadatas[2]
plotMetrics(sm, sm.metadatas[2])


# In[ ]:
