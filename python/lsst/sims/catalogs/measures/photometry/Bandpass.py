""" 
bandpass - 

2/9/2010  ljones@astro.washington.edu

Class data: 
 wavelen (nm)
 sb  (Transmission, 0-1)
 phi (Normalized system response) 
  wavelen/sb are guaranteed gridded. 
  phi will be None until specifically needed; 
     any updates to wavelen/sb within class will reset phi to None. 

Methods: 
 __init__ : pass wavelen/sb arrays and set values (on grid) OR set data to None's
 imsimBandpass : set up a bandpass which is 0 everywhere but one wavelength 
                 (this can be useful for imsim magnitudes)
 readThroughput : set up a bandpass by reading data from a single file
 readThroughtputList : set up a bandpass by reading data from many files and multiplying 
                       the individual throughputs 
 resampleBandpass : use linear interpolation to resample wavelen/sb arrays onto a regular grid 
                    (grid is specified by min/max/step size) 
 sbTophi : calculate phi from sb - needed for calculating magnitudes
 multiplyThroughputs : multiply self.wavelen/sb by given wavelen/sb and return 
                       new wavelen/sb arrays (gridded like self)
 calcZP_t : calculate instrumental zeropoint for this bandpass
 writeThroughput : utility to write bandpass information to file

"""
import warnings as warning
import numpy as n
import Sed  # For ZP_t and M5 calculations. And for 'fast mags' calculation. 

# The following *wavelen* parameters are default values for gridding wavelen/sb/flambda.
MINWAVELEN = 300
MAXWAVELEN = 1200
WAVELENSTEP = 0.1

EXPTIME = 15                      # Default exposure time. (option for method calls).
NEXP = 2                          # Default number of exposures. (option for methods).
EFFAREA = n.pi*(6.5*100/2.0)**2   # Default effective area of primary mirror. (option for methods).
GAIN = 2.3                        # Default gain. (option for method call).
RDNOISE = 5                       # Default value - readnoise electrons or adu per pixel (per exposure)
DARKCURRENT = 0.2                 # Default value - dark current electrons or adu per pixel per second
OTHERNOISE = 4.69                 # Default value - other noise electrons or adu per pixel per exposure
PLATESCALE = 0.2                  # Default value - "/pixel
SEEING = {'u': 0.77, 'g':0.73, 'r':0.70, 'i':0.67, 'z':0.65, 'y':0.63}  # Default seeing values (in ")

class Bandpass:
    """Class for holding and utilizing telescope bandpasses"""    
    def __init__(self, wavelen=None, sb=None,
                 wavelen_min=MINWAVELEN, wavelen_max=MAXWAVELEN, wavelen_step=WAVELENSTEP):
        """Initialize bandpass object, with option to pass wavelen/sb arrays in directly.
        
        Also can specify wavelength grid min/max/step or use default - sb and wavelen will
        be resampled to this grid. If wavelen/sb are given, these will be set, but phi 
        will be set to None. 
        Otherwise all set to None and user should call readThroughput, readThroughputList,
        or imsimBandpass to populate bandpass data."""
        self.wavelen=None
        self.sb=None
        self.phi=None            
        if (wavelen!=None) & (sb!=None):
            self.setBandpass(wavelen, sb, wavelen_min, wavelen_max, wavelen_step)
        return

    ## getters and setters

    def setBandpass(self, wavelen, sb, 
                    wavelen_min=MINWAVELEN, wavelen_max=MAXWAVELEN, wavelen_step=WAVELENSTEP):
        """Populate bandpass data with wavelen/sb arrays.
        
        Sets self.wavelen/sb on a grid of wavelen_min/max/step. Phi set to None."""
        # Check data type.
        if (isinstance(wavelen, n.ndarray)==False) | (isinstance(sb, n.ndarray)==False):
            raise ValueError("Wavelen and sb arrays must be numpy arrays.")
        # Check data matches in length.
        if (len(wavelen)!=len(sb)):  
                raise ValueError("Wavelen and sb arrays must have the same length.")
        # Data seems ok then, make a new copy of this data for self.
        self.wavelen = n.copy(wavelen)
        self.phi = None
        self.sb = n.copy(sb)
        # Resample wavelen/sb onto grid.
        self.resampleBandpass(wavelen_min=wavelen_min, wavelen_max=wavelen_max, wavelen_step=wavelen_step)
        return

    def imsimBandpass(self, imsimwavelen=5000, 
                      wavelen_min=MINWAVELEN, wavelen_max=MAXWAVELEN, wavelen_step=WAVELENSTEP):
        """Populate bandpass data with sb=0 everywhere except sb=1 at imsimwavelen.
        
        Sets wavelen/sb, with grid min/max/step as optional parameters. Does NOT set phi. """
        # Set up arrays.
        self.wavelen = n.arange(wavelen_min, wavelen_max+wavelen_step, wavelen_step, dtype='float')
        self.phi = None
        # Set sb.
        self.sb = n.zeros(len(self.wavelen), dtype='float')
        self.sb[self.wavelen==imsimwavelen] = 1.0
        return

    def readThroughput(self, filename, wavelen_min=MINWAVELEN, wavelen_max=MAXWAVELEN,
                       wavelen_step=WAVELENSTEP):
        """Populate bandpass data with data (wavelen/sb) read from file, resample onto grid.
        
        Sets wavelen/sb, with grid min/max/step as optional parameters. Does NOT set phi."""
        # Set self values to None in case of file read error.
        self.wavelen = None
        self.phi = None
        self.sb = None
        # Check for filename error. 
        # If given list of filenames, pass to (and return from) readThroughputList.
        if isinstance(filename, list):  
            raise warning.warn("Was given list of files, instead of a single file. Using readThroughputList instead")
            self.readThroughputList(componentList=filename, 
                                    wavelen_min=wavelen_min, wavelen_max=wavelen_max, 
                                    wavelen_step=wavelen_step)
        # Filename is single file, now try to open file and read data.
        try:
            f = open(filename, 'r')
        except IOError:
            raise IOError("The throughput file %s does not exist" %(filename))
        # The throughput file should have wavelength(A), throughput(Sb) as first two columns.
        wavelen = []
        sb = []
        for line in f:
            if line.startswith("#"):
                continue
            values = line.split()
            if len(values)<2:
                continue
            wavelen.append(float(values[0]))
            sb.append(float(values[1]))
        f.close()        
        # Set up wavelen/sb.
        self.wavelen = n.array(wavelen, dtype='float')
        self.sb = n.array(sb, dtype='float')
        # Resample throughput onto grid.
        self.resampleBandpass(wavelen_min=wavelen_min, wavelen_max=wavelen_max, wavelen_step=wavelen_step)
        return

    def readThroughputList(self, componentList=['thruputs/detector.dat', 'thruputs/lens1.dat', 
                                                'thruputs/lens2.dat', 'thruputs/lens3.dat', 
                                                'thruputs/m1.dat', 'thruputs/m2.dat', 'thruputs/m3.dat', 
                                                'thruputs/atmos.dat', 'thruputs/ideal_g.dat'],
                           wavelen_min=MINWAVELEN, wavelen_max=MAXWAVELEN, wavelen_step=WAVELENSTEP):
        """Populate bandpass data by reading from a series of files with wavelen/Sb data.

        Multiplies throughputs (sb) from each file to give a final bandpass throughput. 
        Sets wavelen/sb, with grid min/max/step as optional parameters.  Does NOT set phi."""
        # ComponentList = names of files in that directory.
        # A typical component list of all files to build final component list might be: 
        #   componentList=['detector.dat', 'lens1.dat', 'lens2.dat', 'lens3.dat', 
        #                 'm1.dat', 'm2.dat', 'm3.dat', 'atmos.dat', 'ideal_g.dat'] 
        # Set up wavelen/sb on grid.
        self.wavelen = n.arange(wavelen_min, wavelen_max+wavelen_step, wavelen_step, dtype='float')
        self.phi = None
        self.sb = n.ones(len(self.wavelen), dtype='float')
        # Set up a temporary bandpass object to hold data from each file.
        tempbandpass = Bandpass()
        for component in componentList:
            # Read data from file.
            tempbandpass.readThroughput(component, wavelen_min, wavelen_max, wavelen_step)
            # Multiply self by new sb values.
            self.sb = self.sb * tempbandpass.sb
        return

    def getBandpass(self):
        wavelen = n.copy(self.wavelen)
        sb = n.copy(self.sb)
        return wavelen, sb

    ## utilities

    def checkUseSelf(self, wavelen, sb):
        """Simple utility to check if should be using self.wavelen/sb or passed arrays.

        Useful for other methods in this class.
        Also does data integrity check on wavelen/sb if not self."""
        update_self = False
        if (wavelen==None) | (sb==None): 
            # Then one of the arrays was not passed - check if true for both.
            if (wavelen!=None) | (sb!=None):
                # Then only one of the arrays was passed - raise exception.
                raise ValueError("Must either pass *both* wavelen/sb pair, or use self defaults")
            # Okay, neither wavelen or sb was passed in - using self only.
            update_self = True
        else:
            # Both of the arrays were passed in - check their validity.
            if (isinstance(wavelen, n.ndarray)==False) | (isinstance(sb, n.ndarray)==False):
                raise ValueError("Must pass wavelen/sb as numpy arrays")
            if len(wavelen)!=len(sb): 
                raise ValueError("Must pass equal length wavelen/sb arrays")
        return update_self

    def needResample(self, wavelen=None,
                     wavelen_min=MINWAVELEN, wavelen_max=MAXWAVELEN, wavelen_step=WAVELENSTEP):
        """Return true/false of whether wavelen need to be resampled onto a grid.

        Given wavelen OR defaults to self.wavelen/sb - return True/False check on whether
        the arrays need to be resampled to match wavelen_min/max/step grid"""
        # Check if method acting on self or other data.
        update_self = self.checkUseSelf(wavelen, wavelen)
        if update_self:
            wavelen = self.wavelen
        wavelen_max_in = wavelen[len(wavelen)-1]
        wavelen_min_in = wavelen[0]
        wavelen_step_in = wavelen[1]-wavelen[0]
        # Start check if data is already gridded.
        need_regrid=True
        # First check minimum/maximum and first step in array.
        if ((wavelen_min_in == wavelen_min) & (wavelen_max_in == wavelen_max) 
            & (wavelen_step_in == wavelen_step)):
            # Then do a check to see if number of elements consistent with even step size.
            if len(wavelen) == (wavelen_max_in + wavelen_step_in - wavelen_min_in)/wavelen_step_in:
                # Then now decent chance data is gridded properly.
                need_regrid = False
        # At this point, need_grid=True unless it's proven to be False, so return value. 
        return need_regrid


    def resampleBandpass(self, wavelen=None, sb=None,
                         wavelen_min=MINWAVELEN, wavelen_max=MAXWAVELEN, wavelen_step=WAVELENSTEP):
        """Resamples wavelen/sb (or self.wavelen/sb) onto grid defined by min/max/step.

        Either returns wavelen/sb (if given those arrays) or updates wavelen / Sb in self.
        If updating self, resets phi to None"""
        # Is method acting on self.wavelen/sb or passed in wavelen/sb? Sort it out.
        update_self = self.checkUseSelf(wavelen, sb)
        if update_self:
            wavelen = self.wavelen
            sb = self.sb
        # Now, on with the resampling.
        # Set up gridded wavelength.
        wavelen_grid = n.arange(wavelen_min, wavelen_max+wavelen_step, wavelen_step, dtype='float')   
        sb_grid = n.empty(len(wavelen), dtype='float')
        # Do the interpolation of wavelen/sb onto the grid. (note wavelen/sb type failures will die here).
        sb_grid = n.interp(wavelen_grid, wavelen, sb, left=0.0, right=0.0)
        # Update self values if necessary.
        if update_self:
            self.phi = None
            self.wavelen = wavelen_grid
            self.sb = sb_grid
        return wavelen_grid, sb_grid
        
    ## more complicated bandpass functions
    
    def sbTophi(self):
        """Calculate and set phi - the normalized system response.
        
        This function only pdates self.phi"""
        # The definition of phi = (Sb/wavelength)/\int(Sb/wavelength)dlambda.
        # Due to definition of class, self.sb and self.wavelen are guaranteed equal-gridded.
        dlambda = self.wavelen[1]-self.wavelen[0]
        self.phi = self.sb/self.wavelen
        # Normalize phi so that the integral of phi is 1.
        norm = self.phi.sum() * dlambda
        self.phi = self.phi / norm
        return 

    def multiplyThroughputs(self, wavelen_other, sb_other):
        """Multiply self.sb by another wavelen/sb pair, return wavelen/sb arrays.

        The returned arrays will be gridded like this bandpass.
        This method does not affect self."""
        # Resample wavelen_other/sb_other to match this bandpass.
        if self.needResample(wavelen=wavelen_other,
                             wavelen_min=self.wavelen.min(), wavelen_max=self.wavelen.max(),
                             wavelen_step=self.wavelen[1]-self.wavelen[0]):
            wavelen_other, sb_other = self.resampleBandpass(wavelen=wavelen_other, sb=sb_other, 
                                                            wavelen_min=self.wavelen.min(), 
                                                            wavelen_max=self.wavelen.max(), 
                                                            wavelen_step=self.wavelen[1]-self.wavelen[0])
        # Make new memory copy of wavelen. 
        wavelen_new = n.copy(self.wavelen)
        # Calculate new transmission - this is also new memory.
        sb_new = self.sb * sb_other
        return wavelen_new, sb_new

    def calcZP_t(self, expTime=EXPTIME, effarea=EFFAREA, gain=GAIN):
        """Calculate the instrumental zeropoint for a bandpass."""
        # ZP_t is the magnitude of a (F_nu flat) source which produced 1 count per second.
        # This is often also known as the 'instrumental zeropoint'. 
        # Set gain to 1 if want to explore photo-electrons rather than adu.
        # The typical LSST exposure time is 15s/30s, but zp_t definition is for 1s.
        # SED class uses flambda in ergs/cm^2/s/nm, so need effarea in cm^2.
        #  
        # Check dlambda value for integral.
        dlambda = self.wavelen[1] - self.wavelen[0]
        # Set up flat source of arbitrary brightness,
        #   but where the units of fnu are Jansky (for AB mag zeropoint = -8.9).
        flatsource = Sed.Sed()
        flatsource.setFlatSED()
        adu = flatsource.calcADU(self, expTime=expTime, effarea=effarea, gain=gain)
        # Scale fnu so that adu is 1 count/expTime.
        flatsource.fnu = flatsource.fnu * (1/adu)
        # Now need to calculate AB magnitude of the source with this fnu.
        if self.phi == None:
            self.sbTophi()        
        zp_t = flatsource.calcMag(self)
        return zp_t
    
    def calcM5(self, skysed, hardware, expTime=EXPTIME, nexp=NEXP, readnoise=RDNOISE,
               darkcurrent=DARKCURRENT, othernoise=OTHERNOISE,
               seeing=SEEING['r'], platescale=PLATESCALE, 
               gain=GAIN, effarea=EFFAREA):
        """Calculate the AB magnitude of a 5-sigma above sky background source.
        
        Pass into this function the bandpass, hardware only of bandpass, and sky sed objects.
        The exposure time, nexp, readnoise, darkcurrent, gain,
        seeing and platescale are also necessary. """
        # This calculation comes from equation #42 in the SNR document.
        snr = 5.0
        noise_instr = n.sqrt(nexp*readnoise**2 + darkcurrent*expTime*nexp + nexp*othernoise**2)
        neff = 2.436 * (seeing/platescale)**2
        # Calculate the sky counts. Note that the atmosphere should not be included in sky counts.
        skycounts = skysed.calcADU(hardware, expTime=expTime*nexp, effarea=effarea, gain=gain)
        skycounts = skycounts * platescale * platescale
        # Calculate the sky noise.
        skynoise  = n.sqrt(skycounts/gain)
        v_n = neff* (skynoise**2 + noise_instr**2)
        counts_5sigma = (snr**2)/2.0/gain + n.sqrt((snr**4)/4.0/gain + (snr**2)*v_n)
        # Create a flat fnu source that has the required counts (in electrons) in this bandpass.
        flatsource = sed.Sed()
        flatsource.setFlatSED()
        counts_flat = flatsource.calcADU(self, expTime=expTime*nexp, effarea=effarea, gain=gain)
        flatsource.multiplyFluxNorm(counts_5sigma/counts_flat)
        # Calculate the AB magnitude of this source.
        mag_5sigma = flatsource.calcMag(self)
        return mag_5sigma


    def calcEffWavelen(self):
        """Calculate effective wavelengths for filters"""
        # This is useful for summary numbers for filters.
        # Calculate effective wavelength of filters.
        if self.phi==None:
            self.sbTophi()
        effwavelenphi = (self.wavelen*self.phi).sum()/self.phi.sum() 
        effwavelensb = (self.wavelen*self.sb).sum()/self.sb.sum()
        return effwavelenphi, effwavelensb

    def writeThroughput(self, filename, write_phi=False):
        """Write throughput to a file"""
        # Useful if you build a throughput up from components and need to record the combined value.
        f = open(filename, 'w')
        # Print header.
        if write_phi:
            if self.phi==None:
                self.sbTophi()
            print >>f, "# Wavelength(A)  Throughput   Phi"
        else:
            print >>f, "# Wavelength(A)  Throughput"
        # Loop through data, printing out to file.
        for i in range(0, len(self.wavelen), 1):
            if write_phi:
                print >> f, self.wavelen[i], self.sb[i], self.phi[i]
            else:
                print >> f, self.wavelen[i], self.sb[i]
        f.close()
        return


## Bonus, many-magnitude calculation for many SEDs with a single bandpass
    
    def manyMagCalc(self, sedlist):
        """Calculate many magnitudes for many seds using a single bandpass."""
        # Set up limits for wavelength and check bandpass prepared for magnitude calculation.
        minwavelen = self.wavelen[0]
        maxwavelen = self.wavelen[len(self.wavelen)-1]
        stepwavelen = self.wavelen[1] - self.wavelen[0]
        if self.phi == None:
            self.sbTophi()
        # Get seds in compatible wavelength range format.
        for sed in sedlist:
            wavelen, fnu = sed.flambdaTofnu(sed.wavelen, sed.flambda, wavelen_min=minwavelen,
                                            wavelen_max = maxwavelen, wavelen_step=stepwavelen)
        # TODO
        return