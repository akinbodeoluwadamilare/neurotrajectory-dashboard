NeuroTrajectory — Step 4 Dashboard Skeleton

Expected project data:
data/processed/oasis_longitudinal_analysis_ready.csv

Install:
    pip install dash pandas plotly numpy

Run:
    python app.py

Then open the local Dash URL printed in the terminal.

Included:
- app.py
- assets/style.css

Current interactions:
- diagnostic-group, sex, age, education and SES filters
- all-visits / baseline-only cohort scatter mode
- click or lasso selection from cohort scatter
- manual multi-subject selector (maximum 5 used in linked views)
- coordinated nWBV, MMSE and CDR trajectories
- distribution metric switcher
- baseline distributions for nWBV/MMSE/eTIV
- latest-follow-up distributions for Delta_nWBV/Delta_MMSE
- selected subject/visit detail table

Design rule:
Diagnostic-group color is fixed globally:
Nondemented = blue
Converted = orange
Demented = reddish purple


NeuroTrajectory — Step 4.1 refinement

Changes:
- shorter trajectory legends (Subject ID only)
- cohort scatter height reduced to 460 px
- trajectory and distribution panels set to 390 px
- Clear selection button
- status card now distinguishes subjects, filtered visit records, and displayed points
- human-readable details-table headers
- cleaner numeric precision
- existing MMSE 0–30 behavior retained unchanged

Expected data:
data/processed/oasis_longitudinal_analysis_ready.csv

Run:
    python app.py



NeuroTrajectory — Step 4.2

Key updates
-----------
1. Canonical linked subject-selection state
   - hard maximum of five subjects
   - dropdown can never remain above five
   - clicking a selected point toggles it off
   - lasso selection replaces the current selection
   - filter changes prune invalid selected subjects

2. Cross-view linking
   - cohort scatter -> subject selection
   - group distribution -> subject selection
   - selected subjects are highlighted in BOTH views
   - trajectories and details table use the same selection

3. Group distribution interaction
   - box summary + selectable jittered subject points
   - click/lasso enabled
   - one-observation-per-subject note

4. SES clarity
   - interface explicitly reports whether Unknown SES is included/excluded

5. Selection feedback
   - "5 selected (maximum)" message when cap is reached

Expected data
-------------
data/processed/oasis_longitudinal_analysis_ready.csv

Run
---
python app.py



NeuroTrajectory — Step 4.2 FIXED

This build fixes the callback errors in the previous Step 4.2 package.

Root causes fixed
-----------------
1. Dash 4.4.x compatibility
   - removed ctx.triggered_prop_id
   - uses ctx.triggered[0]["prop_id"], which works with the installed Dash

2. Circular dependency removed
   - removed selection-store
   - subject-selector is now the single canonical subject-selection state
   - no Store -> Dropdown -> Store callback cycle

Selection behavior
------------------
- click scatter point: toggle subject
- lasso scatter points: replace selection, maximum 5
- click distribution point: toggle subject
- lasso distribution points: replace selection, maximum 5
- Clear selection: clear all
- filter change: prune subjects no longer in filtered cohort
- manual dropdown: once 5 are selected, all other options are disabled

Cross-view linking
------------------
Selected subjects are shared by:
- cohort scatter
- group distribution
- nWBV trajectory
- MMSE trajectory
- CDR trajectory
- details table

Expected data
-------------
data/processed/oasis_longitudinal_analysis_ready.csv

Run
---
python app.py



NeuroTrajectory — Step 4.3 interaction polish and robustness

Updates
-------
- selections persist when switching distribution metric
- selections persist when switching All visits / Baseline only
- scatter zoom/pan persists across selection changes
- scatter zoom resets when observation mode or filtered cohort changes
- distribution zoom persists across selection changes
- distribution zoom resets when metric or filtered cohort changes
- trajectory zoom resets when selected subject set changes
- lasso > 5 shows: "Selection truncated to first 5 subjects."
- point-click at the cap shows: "Maximum of 5 selected subjects reached."
- filter changes prune only invalid selected subjects and report which were removed
- explicit interaction status message area
- improved narrow/mobile layout

Suggested robustness checks
---------------------------
1. Select 3 subjects, switch nWBV -> MMSE -> Delta_nWBV:
   selection should remain unchanged.

2. Select subjects, switch All visits <-> Baseline only:
   selection should remain unchanged.

3. Zoom cohort scatter, select/deselect subjects:
   zoom should remain.

4. Change age/group/sex filter:
   cohort zoom may reset and invalid selected subjects should be pruned cleanly.

5. Lasso > 5 subjects:
   exactly 5 selected and truncation message shown.

6. Resize browser to narrow width:
   filters/status/panels should stack vertically.

Run
---
python app.py



NeuroTrajectory — Step 5: Global Filtering

Global filters
--------------
- Diagnostic group
- Age range
- Sex
- SES
- Visit range
- Education range (retained from the existing interface)

Core behavior
-------------
A single filtered dataframe now drives:
- cohort status counts
- Age vs nWBV scatter
- eligible subject selector options
- selected-subject nWBV trajectory
- selected-subject MMSE trajectory
- selected-subject CDR trajectory
- group distribution
- selected subject/visit details
- selection pruning

Visit-range semantics
---------------------
Visit range is a true row-level global filter.

Example:
    Visits 2–3

Only rows from Visits 2 and 3 remain available to linked views.

Baseline views:
- true baseline is MR Delay == 0 / Visit 1
- if Visit 1 is excluded, baseline-only scatter/distributions do NOT
  silently pull baseline data from outside the filtered dataframe

Delta distributions:
- latest follow-up means the latest available row inside the active
  filtered dataframe

Suggested tests
---------------
1. Set Visit range 2–3:
   - counts should decrease
   - trajectories/details should show only Visits 2–3
   - baseline-only scatter/distribution should report baseline excluded

2. Set Group=Demented only:
   - every relevant view should update to Demented records only

3. Narrow Age / Sex / SES:
   - counts, scatter, distributions, subject options, details all update

4. Select subjects, then tighten filters:
   - subjects no longer in the filtered dataframe should be pruned

Run
---
python app.py


NeuroTrajectory — Step 6: Subject Selection and Linked Highlighting

Core interaction
----------------
A scatterplot point carries Subject ID in customdata[0].

When the user clicks a point:
1. Dash receives cohort-scatter.clickData.
2. Subject ID is read from customdata[0].
3. The Subject ID is added to/toggled in the shared subject-selector state.
4. The main dashboard callback receives the updated selected-subject list.
5. The following linked views update using the active globally filtered dataframe:
   - Age vs nWBV scatter highlighting
   - nWBV trajectory
   - MMSE trajectory
   - CDR trajectory
   - group-distribution highlighting
   - visit-details table

Selection behavior
------------------
- click: toggle one Subject ID
- lasso: replace selection with up to 5 unique Subject IDs
- manual subject selector remains available
- global filters prune selected subjects that no longer survive
- scatter observation mode and distribution metric do not clear selection
- linked highlighting uses darker/larger points with outlines

Important Step 5 + Step 6 relationship
--------------------------------------
Global filtering happens first.

The selected-subject trajectories and details are drawn only from rows that
survive the active global filters, including Visit range.

Suggested tests
---------------
1. Click one scatter point:
   - one Subject ID appears in selector
   - all visits for that subject that survive the filters appear in trajectory panels
   - details table updates to that subject
   - selected marks remain highlighted

2. Click a second subject:
   - both subjects appear in linked panels

3. Click a selected subject again:
   - it is removed from the linked selection

4. Lasso several points:
   - unique Subject IDs, not visit rows, determine the selected-subject set

5. Tighten global filters:
   - selected subjects outside the filtered dataframe are pruned

Run
---
python app.py



NeuroTrajectory — Step 7: Brushing / Multi-Selection

What Step 7 adds
----------------
1. Lasso / box brushing on the Age vs nWBV scatter
   - selectedData is converted to unique Subject IDs
   - maximum 5 subjects are retained
   - brushing several visit-points from the same participant still selects
     that participant only once

2. Brushing on the group-distribution points
   - selected subject IDs propagate to the same shared selection state

3. Selected subjects continue to update:
   - nWBV trajectories
   - MMSE trajectories
   - CDR trajectories
   - visit-details table
   - cohort scatter highlighting
   - distribution highlighting

4. Selected-vs-remaining cohort comparison
   The distribution panel now has:
       Diagnostic group
       Selected vs remaining

   "Selected vs remaining" compares the brushed subjects against all other
   subjects that survive the active global filters.

Recommended test
----------------
1. Set the scatter toolbar to Lasso or Box Select.
2. Brush around several points.
3. Verify:
   - unique Subject IDs appear in selector
   - max 5 subjects
   - trajectories show selected subjects
   - selected points are emphasized
4. In Group distribution choose "Selected vs remaining".
5. Switch metric between nWBV / MMSE / Delta values.
6. Verify the selected group remains linked while the remaining cohort is
   shown as the comparison population.

Run
---
python app.py


NeuroTrajectory — Step 7 Brushing Stability Fix

Fixes trajectory panels disappearing after box/lasso selection.

Cause:
Plotly may emit selectedData=None or an empty points list when the scatter
redraws after a valid selection. The old callback treated that as an empty
selection and cleared the selected subjects.

Fix:
- Ignore empty/reset selectedData events.
- Clear subjects only with the explicit Clear selection button.
- Preserve valid brush selections during figure redraws.
- Keep click toggling and filter pruning unchanged.
- Add selectionrevision to scatter/distribution layouts.

Test:
1. Box-select 2–5 scatter points.
2. Confirm trajectories appear.
3. Wait for redraws — trajectories should remain.
4. Switch distribution metric — trajectories should remain.
5. Click Clear selection — trajectories should clear intentionally.



NeuroTrajectory — Step 8: Visual Comparison States

Core analytical workflow
------------------------
Full cohort -> Filter -> Brush -> Compare

Visual states
-------------
1. Full cohort
   - faint gray marks
   - reference context only

2. Filtered cohort
   - diagnostic-group colors
   - active analytical population
   - all global filters apply

3. Selected subjects
   - larger, fully opaque, outlined marks
   - linked to nWBV/MMSE/CDR trajectories and details

Selected vs remaining
---------------------
The distribution panel comparison uses:

Selected subjects
versus
Remaining subjects in the ACTIVE FILTERED COHORT

Excluded records are not silently reintroduced.

State strip
-----------
The dashboard now reports:
- total full-cohort subject count
- filtered-cohort subject count
- selected-subject count
- number of remaining comparison subjects

Recommended validation
----------------------
1. Start with all filters open.
2. Confirm Full cohort and Filtered cohort counts match.
3. Tighten age/group/sex/SES/visit filters.
4. Confirm Filtered cohort count falls while Full cohort stays fixed.
5. Brush several participants.
6. Confirm Selected count rises and Remaining count updates.
7. Switch distribution to Selected vs remaining.
8. Verify selected subjects are compared only with the remaining
   filtered cohort.

Run
---
python app.py


NeuroTrajectory — Prototype-Style Boxplots 

This rebuild starts from the known-good Step 8 ComparisonStates app.py
and replaces ONLY create_group_distribution().

Preserved from Steps 5–8:
- diagnostic group / sex / age / visit / education / SES filters
- filtered dataframe semantics
- click-to-select Subject ID
- linked nWBV / MMSE / CDR trajectories
- visit-details table
- box/lasso multi-selection
- max-5 selection state
- stable selection after Plotly redraw
- full cohort / filtered cohort / selected-subject state strip
- Selected vs remaining comparison mode
- details-on-demand hover
- responsive layout

Distribution update:
- prototype-style box traces
- boxpoints='all'
- jitter=0.28
- pointpos=0
- subject-level point hover
- transparent median hotspot with n, Q1, median, Q3, min, max

The previous NameError was caused by accidentally removing the
DETAIL_COLUMNS constant block. This build preserves it.

Run:
    python app.py



NeuroTrajectory — Prototype-Style Boxplots FIXED2

Fix:
Plotly Box.marker.line.width accepts only a scalar number.
The previous build incorrectly passed a per-point list, causing a callback error.

This build:
- uses width=0 on the box trace
- adds a separate scatter overlay for selected observations
- preserves prototype-style boxpoints='all', jitter=0.28, pointpos=0
- preserves summary-statistic hover at the median
- preserves Steps 5–8 functionality

Run:
    python app.py



NeuroTrajectory — Prototype-Style Boxplots FIXED2

Fix:
Plotly Box.marker.line.width accepts only a scalar number.
The previous build incorrectly passed a per-point list, causing a callback error.

This build:
- uses width=0 on the box trace
- adds a separate scatter overlay for selected observations
- preserves prototype-style boxpoints='all', jitter=0.28, pointpos=0
- preserves summary-statistic hover at the median
- preserves Steps 5–8 functionality

Run:
    python app.py



NeuroTrajectory — Final Refinement Phase 3

Built on Phase 2 and preserves its selection/highlight and boxplot refinements.

Added:
- final project title hierarchy at the top of the dashboard
- full subtitle:
  Interactive Visual Analytics for Exploring Longitudinal Brain Atrophy
  and Cognitive Decline in Aging and Dementia
- supporting explanatory sentence about brain volume, cognition, dementia
  severity, participant characteristics, and repeated OASIS-2 visits
- explicit exploratory-only / not-diagnostic framing
- visible Years from Baseline note:
  MR Delay ÷ 365.25
- explicit explanation that visit numbers are not assumed equally spaced
- trajectory x-axis wording standardized to Years from Baseline

Run:
    python app.py




NeuroTrajectory — Final Refinement Phase 5

Fixes based on presentation testing:

1. Trajectory unified-hover box
   - shortened labels so nWBV and other fields fit cleanly
   - preserved Subject, Group, Visit, Years, Age, nWBV, MMSE, CDR
   - explicit white hover styling for readability

2. Legend isolation
   - single-click = hide/show a subject
   - double-click = isolate the clicked subject
   - explicit Plotly legend itemclick/itemdoubleclick configuration

3. Group-distribution median
   - median is calculated from the exact rows used by the box
   - dark horizontal center tick anchors the median visually
   - small open diamond is only the hover target for distribution summary
   - hover reports n, Q1, median, Q3, min, max

For the selected subjects shown during testing:
OAS2_0012, OAS2_0013, OAS2_0029, OAS2_0031, OAS2_0039
the latest-follow-up Delta_nWBV median is -0.008872.

Run:
    python app.py



NeuroTrajectory — Final Refinement Phase 7

Why this change:
The local Plotly/Dash runtime did not reliably honor built-in legend
double-click isolation, even with itemdoubleclick="toggleothers".

Final interaction design:
- Legend single-click remains available for hide/show where supported.
- A new explicit Trajectory focus dropdown reliably isolates one selected
  subject across nWBV, MMSE, and CDR simultaneously.
- Choosing "All selected subjects" restores the full selected comparison.
- The details table and selection state remain unchanged; only the three
  trajectory charts are focused.

This is more predictable for a final presentation than relying on browser-
specific legend double-click behavior.

Run:
    python app.py


NeuroTrajectory — Final Refinement Phase 8

Removed:
- trajectory interaction guidance strip
- unified x-hover on trajectory charts
- legend double-click isolation behavior/claims
- doubleClickDelay settings

Retained:
- ordinary point-level hover (closest)
- single-click legend hide/show
- Trajectory focus dropdown for reliable one-subject isolation
- Years from Baseline explanation near the top of the dashboard
- distribution median summary
- all existing filters, selections, brushing, linked views, and details table

Rationale:
The unified hover obscured too much of the visualization and legend
double-click isolation was unreliable in the local Dash/Plotly runtime.
The explicit Trajectory focus control remains the reliable isolation method.

Run:
    python app.py



NeuroTrajectory — Final Refinement Phase 9

Added a compact Active Cohort Summary strip.

Metrics:
- Subjects: unique participants surviving active filters
- Visits: filtered visit records
- Median nWBV: median across filtered visit records
- Median MMSE: median across filtered visit records
- Median age: median across filtered visit records
- Nondemented: unique subjects
- Converted: unique subjects
- Demented: unique subjects

The summary updates automatically from the same filtered dataframe
used by the dashboard.

Run:
    python app.py


NeuroTrajectory — Final Refinement Phase 10

Redundancy cleanup:
1. Active cohort -> Active filters.
2. Removed subject/visit counts from Active filters.
3. Retained all 8 cohort-summary cards.
4. Visits -> Visit records.
5. Removed standalone cohort-status card.
6. Scatter observations + Selected subjects now occupy the freed row.
7. Compressed Full -> Filtered -> Selected state strip.
8. Diagnostic-group counts remain only in the summary cards.

Run:
    python app.py



NeuroTrajectory — Final Refinement Phase 11

Group Distribution chart only:
- shorter dynamic titles
- corrected top spacing and left-aligned title
- box fill opacity reduced from 0.42 to 0.24
- raw points increased to 0.72 opacity and size 6.5
- selected point overlay slightly refined
- all Phase 10 functionality preserved

Run:
    python app.py


    