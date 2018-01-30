def tsv2subjectinfo(in_file, exclude=None):
    """
    Function to go from events tsv to subjectinfo,
    which can then be passed to model setup functions
    """

    import pandas as pd
    from nipype.interfaces.base import Bunch
    import numpy as np

    events = pd.read_csv(in_file, sep=str('\t'))

    if exclude is not None:  # not tested
        events.drop(exclude, axis=1, inplace=True)

    conditions = sorted(events['trial_type'].unique())
    onsets = [events['onset'][events['trial_type'] == tt].tolist() for tt in conditions]
    durations = [events['duration'][events['trial_type'] == tt].tolist() for tt in conditions]
    
    if 'weight' in events.columns:
      amplitudes = [events['weight'][events['trial_type'] == tt].tolist() for tt in conditions]
    else:
      amplitudes = [np.ones(len(d)) for d in durations]

    bunch = Bunch(conditions=conditions,
                  onsets=onsets,
                  durations=durations,
                  amplitudes=amplitudes)
    
    return bunch

def pickfirst(l):
    return l[0]

def get_files(subject_id, session, task, raw_data_dir, preprocessed_data_dir):
    """
    Given some information, retrieve all the files and metadata from a
    BIDS-formatted dataset that will be passed to the analysis pipeline.
    """
    from bids.grabbids import BIDSLayout
    
    # only the raw files have the correct metadata, eg TR, and the event files are here
    raw_layout = BIDSLayout(raw_data_dir)
    preproc_layout = BIDSLayout(preprocessed_data_dir)

    subjects = preproc_layout.get_subjects()
    assert(subject_id in subjects and subject_id in raw_layout.get_subjects())

    sessions = preproc_layout.get_sessions()
    assert(session in sessions)

    tasks = preproc_layout.get_tasks()
    assert(task in tasks)

    print(subjects, tasks, sessions)
    
    bolds = [f.filename for f in preproc_layout.get(subject=subject_id, modality='func', type='preproc', 
                              session=session, task=task, extensions=['nii.gz'])]
    print(bolds, sep="\n", end="\n")

    masks = [f.filename for f in preproc_layout.get(subject=subject_id, modality='func', type='brainmask', 
                              session=session, task=task, extensions=['nii.gz'])]
    print(masks, sep="\n", end="\n")

    eventfiles =  [f.filename for f in raw_layout.get(subject=subject_id, modality="func",
                              task=task, session=session, extensions=['tsv'])]
    print(eventfiles, sep="\n", end="\n")

    TRs = [raw_layout.get_metadata(f.filename)['RepetitionTime'] for f in raw_layout.get(subject=subject_id,
      type="bold", modality="func", task=task, session=session, 
      extensions=['nii.gz'])]
    print(TRs, sep="\n", end="\n")

    assert(len(bolds)==len(masks)==len(eventfiles)==len(TRs)>0)
    assert(TRs.count(TRs[0])==len(TRs)) # all runs for a particular task must have the same TR

    TR = TRs[0]

    print(list(zip(bolds, masks, eventfiles, TRs)))

    return bolds, masks, eventfiles, TR

def get_files_spm(subject_id, session, task, raw_data_dir):
    """
    Given some information, retrieve all the files and metadata from a
    BIDS-formatted dataset that will be passed to an SPM-based analysis pipeline.
    """
    from bids.grabbids import BIDSLayout
    from utils import tsv2subjectinfo

    layout = BIDSLayout(raw_data_dir)

    subjects = layout.get_subjects()
    assert(subject_id in subjects and subject_id in layout.get_subjects())

    sessions = layout.get_sessions()
    assert(session in sessions)

    tasks = layout.get_tasks()
    assert(task in tasks)

    print(subjects, tasks, sessions)
    
    bolds = [f.filename for f in layout.get(subject=subject_id, modality='func', type='bold', 
                              session=session, task=task, extensions=['nii'])]

    struct = layout.get(subject=subject_id, modality='anat', session=session, type='T1w', extensions=['nii'])[0].filename

    print(struct, "\n", bolds, end="\n")

    eventfiles =  [f.filename for f in layout.get(subject=subject_id, modality="func",
                              task=task, session=session, extensions=['tsv'])]
    eventbunches = [tsv2subjectinfo(f) for f in eventfiles]
    print(eventfiles, eventbunches, sep="\n", end="\n")

    TRs = [layout.get_metadata(f.filename)['RepetitionTime'] for f in layout.get(subject=subject_id,
      type="bold", modality="func", task=task, session=session, extensions=['nii'])]
    print(TRs, end="\n")

    assert(len(bolds)==len(eventfiles)==len(TRs)>0)
    assert(TRs.count(TRs[0])==len(TRs)) # all runs for a particular task must have the same TR

    TR = TRs[0]

    print(list(zip(bolds, eventfiles, eventbunches, TRs)))

    return bolds, struct, eventbunches, TR
