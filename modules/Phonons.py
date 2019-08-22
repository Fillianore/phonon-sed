import numpy as np

class spectral_energy_density:
    def __init__(self,params):
        self.construct_splits(params)
        self.sed = np.zeros((params.num_splits,
                            self.steps_per_split,
                            sum(params.num_qpoints)))
        self.thz = (np.arange(self.steps_per_split)/
                (self.steps_per_split*params.time_step*params.stride)/1e12)

    def construct_splits(self,params):
        self.reduced_steps = params.num_steps//params.stride
        self.steps_per_split = self.reduced_steps//params.num_splits

    def compute_sed(self,params,lattice,eigen_vectors):
        """
        To avoid a horrible mess of indentations, I broke this up into internal methods 
        that the spectral_energy_density class calls on its self. The basic outline is as
        follows (see ... for the formulation)
        1. Loop over 'splits' (i.e. blocks of data for block averaging)
            read in the vels. and pos. for each split (time average the pos. to get a 
            constant position). Data reading is done in an other method.
            2. Loop over q-points (have to do FT at each q-point)
                3. Loop over basis atoms
                    The sum over FT'ed vx-vy-vz and over all basis atoms is taken care of 
                    in loop '3'

        Development notes:
            FFT's aren't scaled properly and neither is the sed where the qdots are 
            divided by 4*pi*....
            FFT's need scaled to be unitary, i.e. same total energy in freq. and time 
            domains. It's just a part of the conventional way the FFT is calculated

            I can easily add phonon-DoS calculation to this!

            Should I time average the atomic positions to get the unit-cell coord? 
            Or do some other fancy math? I am time averaging right-now ...
        """

        #### DEV ####
        print('\nDEV NOTE: the FFT\'s aren\'t properly scaled yet!\n')
        #### DEV ####

        self.num_unit_cells = lattice.unit_cells.max()
        self.num_basis = lattice.basis_pos.max()
        if params.debug:
            self.num_loops = 1
        else:
            self.num_loops = params.num_splits   
        if params.with_eigs: # do the calculation with eigenvectors
            if self.num_basis != eigen_vectors.natom:
                print('\nERROR: number of basis atoms doesn\'t match the PHONOPY file!\n')
            self.sed_bands = np.zeros((params.num_splits,
                            eigen_vectors.natom*3,
                            self.steps_per_split,
                            sum(params.num_qpoints)))
            self.split_loop_with_eigs(params,lattice,eigen_vectors)
            self.sed_bands_avg = self.sed_bands.sum(axis=0)/self.num_loops
            self.sed_avg = self.sed_bands_avg.sum(axis=0)
            max_freq = len(self.thz)//2
            self.sed_bands_avg = self.sed_bands_avg[:,:max_freq,:]
            self.sed_avg = self.sed_avg[:max_freq,:]
            self.thz = self.thz[:max_freq]
        else: # do the calculation without eigenvectors
            self.loop_over_splits(params,lattice)
            self.sed_avg = self.sed.sum(axis=0)/self.num_loops
            max_freq = len(self.thz)//2
            self.sed_avg = self.sed_avg[:max_freq,:]
            self.thz = self.thz[:max_freq]


    ###############################################################
    ### without eigs
    def loop_over_splits(self,params,lattice):
        self.qdot = np.zeros((self.steps_per_split,sum(lattice.num_qpoints)))
        for i in range(self.num_loops):
            print('\nNow on split {} out {}...\n'.format(i+1,self.num_loops))
            self.loop_index = i
            self.get_simulation_data(params,lattice) 
            self.loop_over_qpoints(params,lattice) 
            self.sed[i,:,:] = self.qdot/(4*np.pi) # scale
    def loop_over_qpoints(self,params,lattice):
        for q in range(sum(lattice.num_qpoints)):
            self.q_index = q
            print('\tNow on q-point {} out of {}:\tq=({:.3f}, {:.3f}, {:.3f})'
                    .format(q+1,sum(lattice.num_qpoints),lattice.qpoints[q,0],
                        lattice.qpoints[q,1],lattice.qpoints[q,2]))
            self.exp_fac = np.tile(lattice.qpoints[q,:],(self.num_unit_cells,1))
            self.exp_fac = np.exp(1j*np.multiply(self.exp_fac,self.cell_vecs).sum(axis=1))
            self.loop_over_basis(params,lattice)
    def loop_over_basis(self,params,lattice):
        for i in range(self.num_basis):
            basis_ids = np.argwhere(lattice.basis_pos == (i+1)).reshape(
                    self.num_unit_cells)
            mass = lattice.masses[i]
            vx = np.fft.fft(self.vels[:,basis_ids,0] # scale
                    .reshape(self.steps_per_split,self.num_unit_cells)
                    *self.exp_fac,axis=0) 
            vy = np.fft.fft(self.vels[:,basis_ids,1] # scale
                    .reshape(self.steps_per_split,self.num_unit_cells)
                    *self.exp_fac,axis=0) 
            vz = np.fft.fft(self.vels[:,basis_ids,2] # scale
                    .reshape(self.steps_per_split,self.num_unit_cells)
                    *self.exp_fac,axis=0) 
            self.qdot[:,self.q_index] = (self.qdot[:,self.q_index]+
                       (abs(vx.sum(axis=1))**2+
                        abs(vy.sum(axis=1))**2+
                        abs(vz.sum(axis=1))**2)
                        /self.num_unit_cells*mass) # scale

    ###############################################################
    ### with eigs
    def split_loop_with_eigs(self,params,lattice,eigen_vectors):
        for i in range(self.num_loops):
            print('\nNow on split {} out {}...\n'.format(i+1,self.num_loops))
            self.loop_index = i
            self.get_simulation_data(params,lattice)
            self.qpoint_loop_with_eigs(params,lattice,eigen_vectors)
    def qpoint_loop_with_eigs(self,params,lattice,eigen_vectors):
        for q in range(sum(lattice.num_qpoints)):
            self.q_index = q
            print('\tNow on q-point {} out of {}:\tq=({:.3f}, {:.3f}, {:.3f})'
                    .format(q+1,sum(lattice.num_qpoints),lattice.qpoints[q,0],
                        lattice.qpoints[q,1],lattice.qpoints[q,2]))
            self.exp_fac = np.tile(lattice.qpoints[q,:],(self.num_unit_cells,1))
            self.exp_fac = np.exp(1j*np.multiply(self.exp_fac,self.cell_vecs).sum(axis=1))
            self.band_loop_with_eigs(params,lattice,eigen_vectors)
    def band_loop_with_eigs(self,params,lattice,eigen_vectors):
        for b in range(eigen_vectors.natom*3): # loop over bands
            print('\t\tband {} out of {}'.format(b+1,self.num_basis*3))
            self.qdot = np.zeros((self.steps_per_split))
            self.band_index = b
            self.ex = eigen_vectors.eig_vecs[self.q_index,b,:,0]
            self.ey = eigen_vectors.eig_vecs[self.q_index,b,:,1]
            self.ez = eigen_vectors.eig_vecs[self.q_index,b,:,2]
            self.basis_loop_with_eigs(params,lattice)
            self.sed_bands[self.loop_index,b,:,self.q_index] = self.qdot/(4*np.pi) # scale
    def basis_loop_with_eigs(self,params,lattice):
        for i in range(self.num_basis):
            basis_ids = np.argwhere(lattice.basis_pos == (i+1)).reshape(
                    self.num_unit_cells)
            mass = lattice.masses[i]
            vels = self.exp_fac*(self.ex[i].conj()*self.vels[:,basis_ids,0]
                    .reshape(self.steps_per_split,self.num_unit_cells)+
                    self.ey[i].conj()*self.vels[:,basis_ids,1]
                    .reshape(self.steps_per_split,self.num_unit_cells)+
                    self.ez[i].conj()*self.vels[:,basis_ids,2]
                    .reshape(self.steps_per_split,self.num_unit_cells)) # scale
            self.qdot[:] = (self.qdot[:]+(abs(vels.sum(axis=1))**2)
                    /self.num_unit_cells*mass) # scale


    ##################################################################
    ### read vels and pos
    def get_simulation_data(self,params,lattice):
        self.vels = params.database['vels'][self.loop_index*self.steps_per_split:
                (self.loop_index+1)*self.steps_per_split,:,:]
        self.pos = params.database['pos'][self.loop_index*self.steps_per_split:
                (self.loop_index+1)*self.steps_per_split,:,:]

        # time average the positions (for now, maybe can do corr. between pos and vels)
        self.cell_vecs = self.pos[:,lattice.cell_ref_ids,:].mean(axis=0) 


