# M49 readability sheet — boss audio (UNSCORED until a human reads)

Rubric per system, 1-5 each: sentence readability · punctuation
usefulness · question detection · paragraph readability · meaning
preservation. Machine F1 is never converted into these scores.

## A. IntelliAI raw (what users see today)

> see this is a text to which I generated from my speech okay and if
> you see it has taken the whole statement or speech as one statement
> so that's where we need to add punctuations and signs … (no marks,
> 1061 chars as one block)

## B. IntelliAI raw + kredor/punctuate-all (M49 leader)

Full text: `boss-kredor.txt`. Opening:

> see, this is a text to which I generated from my speech. okay, and
> if you see it has taken the whole statement or speech as one
> statement. so that's where we need to add punctuations …

## C. IntelliAI raw + felflare-bert

Full text: `boss-felflare.txt`.

## D. Sarvam captured output (QUALITATIVE ONLY — M48 directive)

See M48 evidence `sarvam-boss.txt`. Not a benchmark row; kept for the
side-by-side read only.

| System | Sent. readability | Punct. usefulness | Questions | Paragraphs | Meaning | Overall |
|---|---|---|---|---|---|---|
| A raw | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |
| B kredor | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |
| C felflare | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |
| D Sarvam capture | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |
