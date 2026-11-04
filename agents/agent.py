"""ADK web entrypoint.

`adk web .` loads this module and looks for `root_agent`.
Send any message (for example "run sample") to execute the 8-step QC pipeline
against samples/captions_bad.srt and samples/ad_script.srt.
"""

from agents.pipeline import create_qc_sequential_agent

root_agent = create_qc_sequential_agent()
