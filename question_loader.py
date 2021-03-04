#!/usr/bin/env python3

import csv
import sys
import re
import collections
import multiprocessing
import pathlib
import pickle
import gzip
import os

import tqdm
import jieba
import thai_segmenter
from mutagen.mp3 import MP3
from distractors import get_distractors

PREFIX = "templates/cv-corpus-6.1-2020-12-11/"


def tokenize_sentence(question):
    if question["locale"].startswith("zh-"):
        return jieba.lcut(question["sentence"])
    elif question["locale"].startswith("th"):
        return thai_segmenter.tokenize(question["sentence"])
    elif question["locale"].startswith("tr"):
        res = [ x.replace("ʼ", "'") for x in re.split("(\\w+)", question["sentence"].replace("'", "ʼ")) if x.strip() ]
        return res 
    else:
        return [
            x for x in re.split("(\\w+)", question["sentence"]) if x.strip()
        ]


def process_question(question, word_frequency):
    words = tokenize_sentence(question)
    for word in words:
        word_frequency[word] += 1
    question["tokenized"] = words
    return question


def load_questions(language_name):
    questions = []
    word_frequency = collections.Counter()
    distractors = {}
    with open(PREFIX + language_name + "/validated.tsv") as f:
        r = csv.reader(f, delimiter="\t")
        h = next(r)
        sys.stderr.write("Loading %r...\n" % language_name)
        for row in tqdm.tqdm(r):
            question = dict(zip(h, row))
            mp3 = MP3(PREFIX + language_name + "/clips/" + question["path"])
            question["audio_length"] = mp3.info.length
            question["chars_sec"] = len(question["sentence"]) / float(
                question["audio_length"]
            )
            question = process_question(question, word_frequency)
            questions.append(question)
        
        sys.stderr.write("Done loading.\n")

    # FIXME: This is really slow...
    sys.stderr.write("Generating distractors.\n")
    distractors = get_distractors(word_frequency)
    
    sys.stderr.write("Assigning distractors.\n")
    for question in questions:
        question["distractors"] = {}
        for token in question["tokenized"]:
            question["distractors"][token] = distractors[token]

    sys.stderr.write("Done.\n")

    return language_name, questions, word_frequency


def difficulty_function(question, word_frequency, most_common_word):
    chars_sec = question["chars_sec"]
    word_frequencies = [
        word_frequency[word] / most_common_word[1]
        for word in question["tokenized"]
    ]
    # if they speak fast, but use easy words
    if word_frequencies:
        return chars_sec * -min(word_frequencies)
    else:
        sys.stderr.write(
            "WTF: cannot calculate frequencies for question=%r\n" % question
        )
        return chars_sec


def load_all_languages(languages=None):
    word_frequency = collections.defaultdict(lambda: dict)
    most_common_word = collections.defaultdict(lambda: dict)
    questions = collections.defaultdict(lambda: dict)
    if languages is None:
        languages = [
            language.name for language in pathlib.Path(PREFIX).glob("*")
        ]
    with multiprocessing.Pool(4) as p:
        for lng, lng_questions, lng_word_frequency in p.map(
            load_questions, languages
        ):
            questions[lng] = lng_questions
            word_frequency[lng] = lng_word_frequency
            most_common_word[lng] = word_frequency[lng].most_common(1)[0]
            questions[lng].sort(
                key=lambda question: difficulty_function(
                    question, word_frequency[lng], most_common_word[lng]
                )
            )
    return languages, dict(questions)


def regenerate_cache():
    languages, questions = load_all_languages()
    with gzip.open("cache/languages.pickle.gz", "wb") as languages_f:

        pickle.dump(languages, languages_f)
    for language in questions:
        with gzip.open(
            f"cache/questions__{language}.pickle.gz", "wb"
        ) as questions_f:
            sys.stderr.write("Saving the models...\n")
            pickle.dump(questions[language], questions_f)
    return languages, questions


def load_all_languages_cached():
    try:
        sys.stderr.write("Loading pre-cached question set...\n")
        with gzip.open("cache/languages.pickle.gz", "rb") as languages_f:
            languages = pickle.load(languages_f)
        questions = {}
        question_files = list(pathlib.Path("cache").glob("questions__*"))
        question_files = tqdm.tqdm(question_files)
        for path in question_files:
            with gzip.open(path, "rb") as questions_f:
                # extract whatever's between the __ and the extension
                language = path.name.split("__")[1].split(".")[0]
                questions[language] = pickle.load(questions_f)
    except FileNotFoundError:
        try:
            os.mkdir("cache")
        except FileExistsError:
            pass
        languages, questions = regenerate_cache()
    return languages, questions


if __name__ == "__main__":
    regenerate_cache()
