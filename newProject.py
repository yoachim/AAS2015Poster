import numpy as np
import healpy as hp
import matplotlib.pylab as plt

data = np.load('OutDir/ops1_1140_Count_expMJD_r_and_fieldRA_gt_0_and_fieldRA_lt_0_174533_and_fieldDec_lt_0_and_fieldDec_gt_-0_174533_HEAL.npz')

mapv = data['metricValues']
mapv[data['mask']] = hp.UNSEEN

cbarFormat='%i'

hp.gnomview(mapv, rot=(5.5,-5,0), xsize=300, ysize=300, title='',cbar=False)

ax = plt.gca()
im = ax.get_images()[0]
cb = plt.colorbar(im, shrink=0.75, aspect=25, orientation='horizontal',
                              extend='both', extendrect=True, format=cbarFormat)

cb.set_label('Number of Observations')

cb.solids.set_edgecolor("face")

plt.savefig('OutDir/Nobs_zoom.pdf')
