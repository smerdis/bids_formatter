#!/usr/bin/env python
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
from builtins import str
from builtins import range

import os, datetime, sys

import nipype.interfaces.io as nio           # Data i/o
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import nipype.algorithms.modelgen as model   # model generation

from nipype.interfaces.nipy.preprocess import Trim # Trim leading and trailing volumes

import utils # code by AM specific to this project but multiple workflows

fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

#Set up model fitting workflow (we assume data has been preprocessed with fmriprep)
modelfit = pe.Workflow(name='modelfit')

#Custom interface wrapping function Tsv2subjectinfo
tsv2subjinfo = pe.MapNode(util.Function(function=utils.tsv2subjectinfo, input_names=['events_file', 'exclude', 'confounds_file', 'trim_indices'],
                         output_names=['subject_info']), name="tsv2subjinfo", iterfield=['events_file', 'confounds_file'])
modelspec = pe.MapNode(interface=model.SpecifyModel(), name="modelspec", iterfield=['subject_info'])
level1design = pe.MapNode(interface=fsl.Level1Design(), name="level1design", iterfield=['session_info'])
modelgen = pe.MapNode(interface=fsl.FEATModel(), name='modelgen', iterfield=["fsf_file", "ev_files"])

trim = pe.MapNode(interface=Trim(), name="trim", iterfield=['in_file'])
applymask = pe.MapNode(interface=fsl.ApplyMask(), name="applymask", iterfield=["in_file", "mask_file"])

modelestimate = pe.MapNode(interface=fsl.FILMGLS(), name='modelestimate',
                        iterfield=['design_file', 'in_file', 'tcon_file'])

# combine copes, varcopes, and masks across multiple sessions
copemerge = pe.MapNode(interface=fsl.Merge(dimension='t'), iterfield=['in_files'], name="copemerge")
varcopemerge = pe.MapNode(interface=fsl.Merge(dimension='t'), iterfield=['in_files'], name="varcopemerge")
maskemerge = pe.MapNode(interface=fsl.Merge(dimension='t'), iterfield=['in_files'], name="maskemerge")

# set up and estimate fixed-effects cross-session analysis
level2model = pe.Node(interface=fsl.L2Model(), name='l2model')
flameo = pe.MapNode(interface=fsl.FLAMEO(run_mode='fe'), name="flameo", iterfield=['cope_file', 'var_cope_file'])

modelfit.connect([
    (tsv2subjinfo, modelspec, [('subject_info', 'subject_info')]),
    (trim, modelspec, [('out_file', 'functional_runs')]),
    (modelspec, level1design, [('session_info', 'session_info')]),
    (level1design, modelgen, [('fsf_files', 'fsf_file'),
                              ('ev_files', 'ev_files')]),
    (modelgen, modelestimate, [('design_file', 'design_file'),
                              ('con_file','tcon_file')]),
    (trim, applymask, [('out_file', 'in_file')]),
    (applymask, modelestimate, [('out_file', 'in_file')]),
    (modelestimate, copemerge, [(('copes', utils.sort_copes), 'in_files')]),
    (modelestimate, varcopemerge, [(('varcopes', utils.sort_copes), 'in_files')]),
    (modelestimate, level2model, [(('copes', utils.num_copes), 'num_copes')]),
    (copemerge, flameo, [('merged_file', 'cope_file')]),
    (varcopemerge, flameo, [('merged_file', 'var_cope_file')]),
    (level2model, flameo, [('design_mat', 'design_file'),
                           ('design_con', 't_con_file'),
                           ('design_grp', 'cov_split_file')]),
    (maskemerge, flameo, [(('merged_file', utils.pickfirst),'mask_file')])
])

# Data input and configuration!
BIDSDataGrabber = pe.Node(util.Function(function=utils.get_files, 
      input_names=["subject_id", "session", "task", "raw_data_dir", "preprocessed_data_dir", "space", "run"],
      output_names=["bolds", "masks", "events", "TR", "confounds"]), 
      name="BIDSDataGrabber")

# What event/trial types, if any, to exclude
modelfit.inputs.tsv2subjinfo.exclude = None

modelfit.inputs.modelspec.input_units = 'secs'
modelfit.inputs.modelspec.high_pass_filter_cutoff = 128.

modelfit.inputs.level1design.bases = {'dgamma': {'derivs': False}}
modelfit.inputs.level1design.model_serial_correlations = True

modelfit.inputs.modelestimate.smooth_autocorr = True
modelfit.inputs.modelestimate.mask_size = 5
modelfit.inputs.modelestimate.threshold = 0 # 0 is nipype default, setting until intensity normalization is decided

hemi_wf = pe.Workflow(name="fixedeffects")

# output
datasink = pe.Node(nio.DataSink(), name='datasink')

modelfit.connect([
  (modelgen, datasink, [('design_image', 'design_image'), ('design_file', 'design_file')]),
  (modelestimate, datasink, [('results_dir', 'results_dir')]),
  (applymask, datasink, [('out_file', 'epi_masked_trimmed')]),
  (flameo, datasink, [('stats_dir', 'stats_dir')])
])

hemi_wf.connect([
                    (BIDSDataGrabber, modelfit, [('events', 'tsv2subjinfo.events_file'),
                                              ('confounds', 'tsv2subjinfo.confounds_file'),
                                              ('bolds', 'trim.in_file'),
                                              ('masks', 'applymask.mask_file'),
                                              ('masks', 'maskemerge.in_files'),
                                              ('TR', 'modelspec.time_repetition'),
                                              ('TR', 'level1design.interscan_interval')])
                    ])