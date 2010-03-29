import numpy
import ctypes
import math

slalib = numpy.ctypeslib.load_library("_slalsst.so",".")

class Astrometry():
    """Collection of astrometry routines that operate on numpy arrays"""
    
    def sphericalToCartesian(self, longitude, latitude):
        cosDec = numpy.cos(latitude) 
        return numpy.array([numpy.cos(longitude)*cosDec, 
                          numpy.sin(longitude)*cosDec, 
                          numpy.sin(latitude)])
    def cartesianToSpherical(self, xyz):
        rad = numpy.sqrt(xyz[0][:]*xyz[0][:] + xyz[1][:]*xyz[1][:] + xyz[2][:]*xyz[2][:])

        longitude = numpy.arctan2( xyz[1][:], xyz[0][:])
        latitude = numpy.arctan2( xyz[2][:], rad)

        # if rad == 0
        #latitude = numpy.zeros(len( xyz[0][:])

        return longitude, latitude
    
    def applyPrecession(self, ra, dec, EP0=2000.0, Date=2000.0):
        """ applyPrecession() applies precesion and nutation to coordinates between two epochs.
        
        Assumes FK5 as the coordinate system
        units:  ra_in (radians), dec_in (radians)

        This uses the Fricke IAU 1976 model for J2000 precession
        This uses the IAU 1980 nutation model
        """
        print ra

        raOut = numpy.zeros(len(ra))
        decOut = numpy.zeros(len(ra))
        
        #        self.slalib.slaPreces.argtypes = [ctypes.c_char_p, ctypes.c_double,
        #                                     ctypes.c_double, ctypes.POINTER(ctypes.c_double),
        #                                     ctypes.POINTER(ctypes.c_double)]
        #        for i,raVal in enumerate(ra):
        #            raIn = ctypes.c_double(ra[i])
        #            decIn = ctypes.c_double(dec[i])
        #            self.slalib.slaPreces("FK5", EP0, EP1, ctypes.pointer(raIn),ctypes.pointer(decIn))
        #            raOut[i] = raIn.value
        #            decOut[i] = decIn.value

        # Define rotation matrix and ctypes pointer
        rmat = numpy.array([[0.,0.,0.],[0.,0.,0.],[0.,0.,0.]])
        rmat_ptr = numpy.ctypeslib.ndpointer(dtype=float, ndim=2, shape=(3,3))

        # Determine the precession and nutation
        slalib.slaPrenut.argtypes = [ctypes.c_double,ctypes.c_double, rmat_ptr]
        slalib.slaPrenut(EP0, Date, rmat)

#        self.slalib.slaPrec.argtypes = [ctypes.c_double,ctypes.c_double, rmat_ptr]
#        Date = 1994.89266306
#        self.slalib.slaPrec(EP0, Date, rmat)

        # Apply rotation matrix
        xyz = self.sphericalToCartesian(ra,dec)
        xyz =  numpy.dot(rmat,xyz)

        raOut,decOut = self.cartesianToSpherical(xyz)
        return raOut,decOut

    def applyProperMotion(self, ra, dec, pm_ra, pm_dec, parallax, v_rad, EP0=2000.0, EP1=2015.0):
        """Calculates proper motion between two epochs
        
        Note pm_ra is measured in sky velocity (cos(dec)*dRa/dt). Slalib assumes dRa/dt
        
        units:  ra (radians), dec (radians), pm_ra (radians/year), pm_dec 
        (radians/year), parallax (arcsec), v_rad (km/sec), EP0 (Julian years)
        """

        EPSILON = 1.e-10

        raOut = numpy.zeros(len(ra))
        decOut = numpy.zeros(len(ra))

        #Define proper motion interface
        slalib.slaPm.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                      ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                      ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)] 

        _raOut = ctypes.c_double(0.)
        _decOut = ctypes.c_double(0.)
        for i,raVal in enumerate(ra):
            if ((math.fabs(pm_ra[i]) > EPSILON) or (math.fabs(pm_dec[i]) > EPSILON)):
                slalib.slaPm(ra[i], dec[i], pm_ra[i], pm_dec[i]/numpy.cos(dec[i]), parallax[i],
                                  v_rad[i] ,EP0, EP1, _raOut, _decOut)
                raOut[i] = _raOut.value
                decOut[i] = _decOut.value
            else:
                raOut[i] = ra[i]
                decOut[i] = dec[i]
            
        return raOut,decOut

    def applyMeanApparentPlace(self, ra, dec, pm_ra, pm_dec, parallax, v_rad, Epoch0=2000.0, Date=2015.0):
        """Calulate the Mean Apparent Place given an Ra and Dec

        Optimized to use slalib mappa routines
        Recomputers precession and nutation
        """
        # Define star independent mean to apparent place parameters
        prms = numpy.zeros(21)
        prms_ptr = numpy.ctypeslib.ndpointer(dtype=float, ndim=1, shape=(21))
        slalib.slaMappa.argtypes = [ctypes.c_double,ctypes.c_double, prms_ptr]
        slalib.slaMappa(Epoch0, Date, prms)

        #Apply source independent parameters
        slalib.slaMapqk.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                      ctypes.c_double, ctypes.c_double, prms_ptr,
                                      ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)] 

        raOut = numpy.zeros(len(ra))
        decOut = numpy.zeros(len(ra))

        # Loop over postions and apply corrections
        _raOut = ctypes.c_double(0.)
        _decOut = ctypes.c_double(0.)
        for i,raVal in enumerate(ra):
            slalib.slaMapqk(ra[i], dec[i], pm_ra[i], (pm_dec[i]/numpy.cos(dec[i])), parallax[i],
                            v_rad[i], prms, _raOut, _decOut)
            raOut[i] = _raOut.value
            decOut[i] = _decOut.value

        return raOut,decOut

    def applyMeanObservedPlace(self, ra, dec, Date = 2015.):
        """Calculate the Mean Observed Place

        Optimized to use slalib mappa routines
        Recomputers precession and nutation
        """

        # Correct site longitude for polar motion slaPolmo
        obsPrms = numpy.zeros(14)
        obsPrms_ptr = numpy.ctypeslib.ndpointer(dtype=float, ndim=1, shape=(14))
        slalib.slaAoppa.argtypes= [ ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                         ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                         ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                         ctypes.c_double, obsPrms_ptr]

        wavelength = 5000.
        #
        # TODO NEED UT1 - UTC to be kept as a function of date.
        # Assume dut = 0.3 (seconds)
        dut = 0.3
        slalib.slaAoppa(Date, dut,
                        self.site.parameters["longitude"],
                        self.site.parameters["latitude"],
                        self.site.parameters["height"],
                        self.site.parameters["xPolar"],
                        self.site.parameters["yPolar"],
                        self.site.parameters["meanTemperature"],
                        self.site.parameters["meanPressure"],
                        self.site.parameters["meanHumidity"],
                        wavelength ,
                        self.site.parameters["lapseRate"],
                        obsPrms)
                             

        # slaaopqk to apply to sources self.slalib.slaAopqk.argtypes=
        slalib.slaAopqk.argtypes= [ctypes.c_double, ctypes.c_double, obsPrms_ptr, ctypes.POINTER(ctypes.c_double),
                                   ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                                   ctypes.POINTER(ctypes.c_double),
                                   ctypes.POINTER(ctypes.c_double)]

        raOut = numpy.zeros(len(ra))
        decOut = numpy.zeros(len(ra))

        _raOut = ctypes.c_double(0.)
        _decOut = ctypes.c_double(0.)
        azimuth = ctypes.c_double(0.)
        zenith = ctypes.c_double(0.)
        hourAngle = ctypes.c_double(0.)
        for i,raVal in enumerate(ra):
            slalib.slaAopqk(ra[i], dec[i], obsPrms, azimuth, zenith, hourAngle, _raOut, _decOut)            
            raOut[i] = _raOut.value
            decOut[i] = _decOut.value
            
        return raOut,decOut



    def refractionCoefficients():
        """ Calculate the refraction using Slalib's refco routine

        This calculates the refraction at 2 angles and derives a tanz and tan^3z coefficient for subsequent quick
        calculations. Good for zenith distances < 76 degrees

        Call slalib refz to apply coefficients
        """

        slalib.slaRefco.argtypes= [ ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                    ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                    ctypes.c_double, ctypes.c_double, 
                                    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        
        wavelength = 5000.
        precison = 1.e-10
        slalib.slaRefco(self.site.parameters["height"],
                        self.site.parameters["meanTemperature"],
                        self.site.parameters["meanPressure"],
                        self.site.parameters["meanHumidity"],
                        wavelength ,
                        self.site.parameters["longitude"],
                        self.site.parameters["latitude"],
                        self.site.parameters["lapseRate"],
                        precision,
                        tanzCoeff,
                        tan3zCoeff)

        return tanzCoeff, tan3zCoeff

    def applyRefraction(zenithDistance, tanzCoeff, tan3zCoeff):
        """ Calculted refracted Zenith Distance
        
        uses the quick slalib refco routine which approximates the refractin calculation
        """
        slalib.slaRefz.argtypes= [ ctypes.c_double, ctypes.c_double, ctypes.c_double,
                                   ctypes.POINTER(ctypes.c_double)]
        refractedZenith = 0.0
        slalib.slaRefco(zenithDistance, tanzCoeff, tan3zCoeff, refractedZenith)
        
        return refractedZenith
