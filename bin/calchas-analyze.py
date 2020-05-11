#!/usr/bin/env python3
import os

import click

import streamlit.cli


@click.group()
def main():
    pass


@main.command("streamlit")
def main_streamlit():
    script_path = os.path.abspath(
        os.path.join(
            os.path.dirname(
                os.path.realpath(__file__)
            ),
            os.pardir,
            "src",
            "analyzer.py"
        )
    )

    args = ["-v", "--trips=..", "--remote=pi@zpi:~/git/calchas-git",]
    streamlit.cli._main_run(script_path, args)

if __name__ == "__main__":
    main()
