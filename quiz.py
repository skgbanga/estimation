import math
from typing import Any
from contextlib import suppress
from dataclasses import dataclass, field
from collections import defaultdict

from h2o_wave import app, Q, ui, main  # type: ignore # pylint: disable=unused-import
from h2o_wave import types

qs = [
    dict(label="What number was I thinking this morning?", answer=437),
    dict(
        label="How many times the word 'tunak' comes in Daler Mehndi's song 'tunak tunak Tun'?",
        answer=150,
    ),
    dict(label="Number of dogs in NYC named Yoda?", answer=38),
    dict(
        label="The number of calories you’d be eating if you had “one of everything” from the Cheesecake Factory menu?",
        answer=616325,
    ),
    dict(
        label="Number of citations Sahil has on google scholar?",
        answer=950,
    ),
    dict(
        label="Number of VRBO reviews for the hampton place we stayed in",
        answer=9,
    ),
    dict(
        label="Number of unprovoked shark attacks on humans worldwide in 2021?",
        answer=73,
    ),
    dict(
        label="What is the recommended length (upper limit) of a tiktok video?",
        answer=34,
    ),
    dict(
        label="Number of international trips by Mr. Modi since 2014?",
        answer=109,
    ),
    dict(label="How many times Joey says 'How YOU doin'?", answer=19),
]


@dataclass
class Question:
    num: int
    label: str
    answer: int

    def card(self, player: str) -> types.FormCard:
        return ui.form_card(
            box="1 2 5 3",
            items=[
                ui.text_l(f"{player}: Question {self.num}"),
                ui.text_l(self.label),
                ui.textbox(name="lower"),
                ui.textbox(name="upper"),
                ui.button(name="answer", label="Submit", primary=True),
            ],
        )


QUESTIONS = {i: Question(num=i, **q) for i, q in enumerate(qs)}  # type: ignore


@dataclass
class Answer:
    lower: str
    upper: str

    def correct(self, answer: int) -> bool:
        with suppress(Exception):
            lower = int(self.lower)
            upper = int(self.upper)
            if lower <= answer <= upper:
                return True

        return False

    def score(self, answer: int) -> int:
        assert self.correct(answer)
        return math.ceil(int(self.upper) // int(self.lower))

    def __str__(self) -> str:
        return "[" + self.lower + ", " + self.upper + "]"


@dataclass
class PlayerInfo:
    answers: list[Answer] = field(default_factory=list)


@dataclass
class State:
    total_num_players: int = 2
    total_num_questions: int = len(QUESTIONS)
    players: dict[str, PlayerInfo] = field(
        default_factory=lambda: defaultdict(PlayerInfo)
    )
    question: int = 0
    answered: int = 0
    waiting_finished: int = 0

    @property
    def initialized(self) -> bool:
        return len(self.players) == self.total_num_players

    @property
    def game_finished(self) -> bool:
        return self.question == self.total_num_questions

    @property
    def num_players(self) -> int:
        return len(self.players)


state = State()


def results_card() -> types.FormCard:
    question_fields = list(
        reversed([f"Question{num}" for num in range(state.question)])
    )
    fields = ["Player", "Score", *question_fields]
    rows = []
    min_score = math.inf
    winners = []
    for player, info in state.players.items():
        correct = 0
        score = 0
        answers = []
        for idx, answer in enumerate(info.answers):
            answers.append(str(answer))
            q = QUESTIONS[idx]
            if answer.correct(q.answer):
                correct += 1
                score += answer.score(q.answer) - 1
        total_score = 2 ** (state.question - correct) * (10 + score)
        if total_score < min_score:
            winners = [player]
        elif total_score == min_score:
            winners.append(player)
        min_score = min(min_score, total_score)
        answers = list(reversed(answers))
        rows.append([player, (correct, total_score), *answers])

    def make_markdown_row(values: list[str] | str) -> str:
        return f"| {' | '.join([str(x) for x in values])} |"

    def make_markdown_table(fields: list[str], rows: list[Any]) -> str:
        return "\n".join(
            [
                make_markdown_row(fields),
                make_markdown_row("-" * len(fields)),
                "\n".join([make_markdown_row(row) for row in rows]),
            ]
        )

    items = [
        ui.text("Results"),
        ui.text(make_markdown_table(fields=fields, rows=rows)),
    ]
    if state.game_finished:
        txt = (
            f"Winner: {winners[0]}"
            if len(winners) == 1
            else f"Winners: {','.join(winners)}"
        )
        items.append(ui.text(txt))

    return ui.form_card(
        box="1 5 8 10",
        items=items,
    )


markdown = """=
# Fun-estimation

## Context
- Created by Andy Niedermaier, a trader at Jane Street Capital
- Competition where you compete on Fermi style estimation questions format

## Format
- There are 10 questions total
- Answers must be submitted as closed intervals of the form [a, b] for a ≤ b where a and b must be integers
- No external references are allowed e.g. calculators, phones, internet Scoring
- An interval is correct if it contains the answer
- You start with score 10
- Every correct answer increases the score linearly by `math.ceil(b / a) - 1`
- Every incorrect answer doubles your score
- No submissions to a question counts as incorrect and will double the score
- Player with the lowest score after 10 questions wins

## Logistics
- Scoring will be updated live throughout the contest

## Example

1. Weight of blue whale (tons)

The answer is 155.

- Player1 submits [50, 210]. This contains the answer so the score for the question is 5
- Player2 submits [150, 200]. This contains the answer so the score for the question is 1
- Player3 submits [1, 100]. This does not contain the answer so this is incorrect
- Player4 submits [100, 500000]. This contains the answer, and the score is
  5000. Though in this case, the interval is so wide, it's worse than being
  incorrect!

"""


@app("/quiz")  # type: ignore
async def serve(q: Q) -> None:
    location = q.args["#"]
    if location == "menu/help":
        q.page["help"] = ui.markdown_card(
            box="1 2 5 10",
            title="Help",
            content=markdown,
        )
    else:
        del q.page["help"]

        if q.args.intro:  # collect user information on them giving the name
            if q.args.text and q.args.text not in state.players:
                q.client.name = q.args.text
                _ = state.players[q.args.text]

                while not state.initialized:
                    remaining = state.total_num_players - state.num_players
                    text = f"Waiting for {remaining} player{'s' if remaining > 1 else ''} to join the game..."
                    q.page["form"] = ui.form_card(
                        box="1 2 4 5",
                        items=[
                            ui.text(text),
                        ],
                    )
                    await q.page.save()
                    await q.sleep(1)

        if not q.client.name:  # show intro screen
            q.page["nav"] = ui.tab_card(
                box="1 1 2 1",
                items=[
                    ui.tab(name="#menu/quiz", label="Quiz"),
                    ui.tab(name="#menu/help", label="Help"),
                ],
                value=f"#{location}" if location else None,
            )
            q.page["form"] = ui.form_card(
                box="1 2 5 3",
                items=[
                    ui.textbox(name="text", label="Name"),
                    ui.button(name="intro", label="Submit", primary=True),
                ],
            )
        else:
            name = q.client.name
            if q.args.answer:  # process their answer
                state.players[name].answers.append(
                    Answer(lower=q.args.lower, upper=q.args.upper)
                )
                if state.answered + 1 == state.total_num_players:
                    state.question += 1
                    state.answered += 1
                    state.waiting_finished += 1

                    # we have to wait for all the other players to wake up
                    # before resetting answered back to 0
                    while state.waiting_finished != state.total_num_players:
                        q.page["form"] = ui.form_card(
                            box="1 2 4 5",
                            items=[ui.text("Waiting for other people to resume...")],
                        )
                        await q.page.save()
                        await q.sleep(0.2)

                    state.answered = 0
                    state.waiting_finished = 0
                else:
                    state.answered += 1
                    while state.answered != state.total_num_players:
                        remaining = state.total_num_players - state.answered
                        text = f"Waiting for {remaining} player{'s' if remaining > 1 else ''} to answer..."
                        q.page["form"] = ui.form_card(
                            box="1 2 4 5",
                            items=[
                                ui.text(text),
                            ],
                        )
                        await q.page.save()
                        await q.sleep(1)
                    state.waiting_finished += 1

            # show next question or show results
            if state.game_finished:
                q.page["form"] = ui.form_card(
                    box="1 2 4 5", items=[ui.text("Game finished!")]
                )
                q.page["results"] = results_card()
            else:
                q.page["form"] = QUESTIONS[state.question].card(name)
                q.page["results"] = results_card()

    await q.page.save()
