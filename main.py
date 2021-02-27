#!/usr/bin/env python3

import os
import random
import csv

from flask import Flask, render_template, send_from_directory

app = Flask(__name__, static_url_path="")


def tokenize_sentence(question):
    return question["sentence"].split()


def process_question(question):
    question["sentence"] = tokenize_sentence(question)
    return question


def load_questions():
    questions = []
    with open("templates/cv-corpus-6.1-2020-12-11/fi/validated.tsv") as f:
        r = csv.reader(f, delimiter="\t")
        h = next(r)
        for row in r:
            question = dict(zip(h, row))
            question = process_question(question)
            questions.append(question)
    return questions


questions = load_questions()


def select_clip(questions):
    return random.choice(questions)


@app.route("/get_clips")
def get_clips():
    selected_questions = []
    while len(selected_questions) < 3:
        selected_question = select_clip(questions)
        if selected_question not in selected_questions:
            selected_questions.append(selected_question)
    return {"questions": selected_questions}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("templates", path)


if __name__ == "__main__":
    app.run(port=int(os.environ.get("FLASK_PORT", "5001")), host="0.0.0.0")
