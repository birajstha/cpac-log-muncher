import pathlib as pl
import re
from datetime import datetime
import pandas as pd
import argparse
import numpy as np
from typing import List, Dict, Any

ICO_SUCCESS = "&#9989;"
ICO_FAILURE = "&#10060;"

TEMPLATE_REPORT_MD = """# CPAC run report

{header}

## Summary

{summary}

## Details

{details}

<hr>

{footer}

"""

TEMPLATE_ENTRY_MD = """### {file}

{details}

"""

TEMPLATE_SPOILER_MD = """<details>
<summary>{summary}</summary>

{details}

</details>
"""


def crashfile_to_md(crashfile: pl.Path):
    with open(crashfile, "r") as f:
        crashfile_content = f.read()
        return TEMPLATE_SPOILER_MD.format(
            summary=f"Crashfile <code>{crashfile.name}</code>",
            details=f"```Python\n{crashfile_content}```",
        )


def make_details(stats: Dict[str, Any]):
    crashfiles_md = "\n".join(
        [crashfile_to_md(crashfile) for crashfile in stats["crashfiles"]]
    )

    del stats["crashfiles"]

    details_md = TEMPLATE_ENTRY_MD.format(
        file=stats["pipeline_config"],
        details=pd.DataFrame(
            {"key": stats.keys(), "value": stats.values()}
        ).to_markdown(index=False),
    )

    if not stats["success"]:
        logfile_tail = file_tail(stats["file"], 100)

        crashfiles_md += "\n" + TEMPLATE_SPOILER_MD.format(
            summary="Last 100 lines of logfile",
            details=f"```log\n{logfile_tail}```",
        )

    return details_md + crashfiles_md


def file_tail(file: pl.Path, n: int = 10):
    with open(file, "r", encoding="UTF-8") as f:
        lines = f.readlines()
        return "".join(lines[-n:])


def main():
    parser = argparse.ArgumentParser(description="Generate a report on CPAC runs.")
    parser.add_argument(
        "path", type=str, help="Path to the directory containing the log files."
    )
    parser.add_argument(
        "-o", "--output", type=str, help="Path to the output file.", required=False
    )
    args = parser.parse_args()

    log_files = find_log_files(pl.Path(args.path))
    stats = [extract_info(pl.Path(f)) for f in log_files]

    df = pd.DataFrame.from_records(stats)

    df["success_state"] = df["success"]
    df["success"] = np.where(df["success"], ICO_SUCCESS, ICO_FAILURE)

    df["pipeline_config"] = df["pipeline_config"].apply(lambda x: f"[{x}](#{x})")

    details = "\n".join([make_details(x) for x in stats])

    report = TEMPLATE_REPORT_MD.format(
        header=f"Ran {len(stats)} CPAC pipelines with {df['success_state'].sum() / len(stats) * 100}% success rate.\n\nSlowest pipeline took {df['duration'].max()}.",
        footer=f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        summary=df[["pipeline_config", "duration", "success"]].to_markdown(index=False),
        details=details,
    )

    if args.output:
        with open(args.output, "w", encoding="UTF-8") as f:
            f.write(report)
    else:
        print(report)


# find files called 'pypeline.log' in subdirectories
def find_log_files(root: pl.Path):
    return root.glob("**/pypeline*.log")


RX_TIMESTAMP = re.compile(r"^\d{6}-\d{2}:\d{2}:\d{2},\d{1,3}")
RX_CPAC_COMMAND = re.compile(r"^\s*Run command: (.*)$")
RX_CPAC_VERSION = re.compile(r"^\s*C-PAC version: (.*)$")
RX_CPAC_END_PIPELINE_CONFIG = re.compile(r"^\s*Pipeline configuration: (.*)$")
RX_CPAC_END_SUBJECT_WORKFLOW = re.compile(r"^\s*Subject workflow: (.*)$")

RC_CPAC_END_SUCCESS = re.compile(r"^\s*CPAC run complete:\s*$")
RC_CPAC_END_SUCCESS_TEST_CONFIG = re.compile(r"^\s*the pipeline was built successfully, but was not run\s*$")
RC_CPAC_END_ERROR = re.compile(r"^\s*CPAC run error:\s*$")

RX_CPAC_PIPELINE_CONFIG_COMMAND_FALLBACK = re.compile(r"--preconfig\s*(\S+)")


def extract_info(log_file: pl.Path):
    min_time = None
    max_time = None

    cpac_command = None
    cpac_test_config = None
    cpac_version = None
    cpac_pipeline_config = None
    cpac_subject_workflow = None

    cpac_success = False
    cpac_error = False

    # read line by line
    with open(log_file, "r", encoding="UTF-8") as f:
        while line := f.readline():
            # match with regex
            if match := re.match(RX_TIMESTAMP, line):
                # convert to datetime object
                stamp = datetime.strptime(match.group(), "%y%m%d-%H:%M:%S,%f")

                if min_time is None or stamp < min_time:
                    min_time = stamp
                if max_time is None or stamp > max_time:
                    max_time = stamp

            elif match := re.match(RX_CPAC_COMMAND, line):
                cpac_command = match.group(1)
                cpac_test_config = ' test_config ' in cpac_command
            elif match := re.match(RX_CPAC_VERSION, line):
                cpac_version = match.group(1)
            elif match := re.match(RX_CPAC_END_PIPELINE_CONFIG, line):
                cpac_pipeline_config = match.group(1)
            elif match := re.match(RX_CPAC_END_SUBJECT_WORKFLOW, line):
                cpac_subject_workflow = match.group(1)
            elif (match := re.match(RC_CPAC_END_SUCCESS, line)) or (cpac_test_config and (match := re.match(RC_CPAC_END_SUCCESS_TEST_CONFIG, line))):
                cpac_success = True
            elif match := re.match(RC_CPAC_END_ERROR, line):
                cpac_error = True

    # calculate difference
    if max_time is not None and min_time is not None:
        diff = max_time - min_time

    # fallback to command line argument or filename
    if cpac_pipeline_config is None and not cpac_command is None:
        cpac_pipeline_config = (
            fb.group(1)
            if (fb := re.search(RX_CPAC_PIPELINE_CONFIG_COMMAND_FALLBACK, cpac_command))
            else None
        )
    if cpac_pipeline_config is None:
        cpac_pipeline_config = str(log_file)

    crashfiles = list(log_file.parent.glob("../../crash-*.txt"))

    return {
        "file": log_file,
        "start": min_time,
        "duration": diff,
        "command": cpac_command,
        "version": cpac_version,
        "pipeline_config": cpac_pipeline_config,
        "subject_workflow": cpac_subject_workflow,
        "success": cpac_success and not cpac_error,
        "crashfiles": crashfiles,
    }


if __name__ == "__main__":
    main()
