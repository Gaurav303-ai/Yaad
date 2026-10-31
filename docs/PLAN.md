# Yaad --- Master Plan

## Hinglish-first Meeting-to-Execution Agent

**Hackathon context:** Product Space hackathon\
**USP:** Hinglish, Conflicts, Commitments

## 1. One-line pitch

Indian teams decide things in Hinglish and forget them on WhatsApp. Yaad
listens to the meeting, extracts decisions, owners and deadlines,
catches contradictions with past decisions, asks for confirmation, and
then creates the tasks and reminders itself.

## 2. Product approach

Yaad uses foundation models and focuses on orchestration, memory design
and UX rather than building custom speech models, diarization, vector
pipelines and fine-tuning. It accepts labelled transcripts with an
optional transcription API fallback; uses specialised agents plus a
critic; combines a structured Postgres decision ledger with semantic
search; understands Hinglish relative dates and soft phrases; integrates
Telegram plus one tracker; and tracks commitment reliability per person.

## 3. Agentic architecture

An Orchestrator runs specialised agents. Each agent has one job, a
strict JSON output schema and tools.

  ------------------------------------------------------------------------------------
                     \# Agent            Job                          Tools
  --------------------- ---------------- ---------------------------- ----------------
                      1 Ingest Agent     Clean transcript, normalise  Transcript
                                         speaker names, split into    parser, optional
                                         segments                     audio
                                                                      transcription
                                                                      API

                      2 Extractor Agent  Extract decisions, action    Structured
                                         items, owners, deadlines,    output / JSON
                                         source quote and speaker     schema

                      3 Hinglish         Resolve relative dates using Date tool, team
                        Resolver         meeting date, expand         roster
                                         nicknames, classify          
                                         decision/intent/discussion   
                                         and confidence               

                      4 Memory Agent     Retrieve related past        Postgres,
                                         decisions using structured   pgvector
                                         filters and embeddings       

                      5 Conflict Agent   Compare new decisions with   Memory results
                                         retrieved ones; label        
                                         contradiction, update or     
                                         duplicate and explain        

                      6 Critic Agent     Verify each extracted item   Transcript
                                         against transcript; drop     lookup
                                         unsupported items            

                      7 Action Agent     After human approval, create Trello / GitHub
                                         tracker tasks and schedule   Issues API,
                                         reminders                    scheduler

                      8 Digest Agent     Weekly per-person summary of DB queries,
                                         due soon, overdue and new    email/Telegram
                                         decisions                    
  ------------------------------------------------------------------------------------

**Human-in-the-loop:** Nothing is posted until the user approves, edits
or rejects each item.

**Pipeline:** Meeting → Ingest → Extractor → Hinglish Resolver → Critic
→ Memory + Conflict → Review → Approve → Action → Tracker + Reminders →
Weekly Digest.

## 4. Technology stack

The original PDF specifies: - Frontend: Next.js, Tailwind, shadcn/ui,
Framer Motion. - Backend: Next.js API routes; Python FastAPI as an
alternative. - LLM: Claude API (verify model identifier in provider
documentation). - Database and memory: Supabase Postgres + pgvector +
auth. - Tracker: Trello or GitHub Issues; choose one. - Messaging:
Telegram bot; WhatsApp Business API is roadmap. - Email digest:
Resend. - Scheduling: Vercel Cron or Supabase scheduled functions. -
Deployment: Vercel app + Supabase data.

**Implementation note:** The subsequently selected project setup uses
React + Python/FastAPI + Gemini + Supabase. This is an implementation
change from the original PDF, not the original PDF's stated stack.

## 5. Meeting entry modes and lifecycle

1.  Live Replay Meeting Room: scripted Hinglish transcript streams line
    by line; transcript on left, extracted cards on right.
2.  Upload/paste transcript: accepts Zoom, Meet or Otter-style text with
    speaker labels.
3.  Audio upload (bonus): send audio to a transcription API supporting
    Hindi/English code-mixing, then process as transcript.

Lifecycle: create meeting (title, date, attendees); start replay or
upload; run agents; review/approve/edit/reject; approved items become
tracker tasks and reminders; store meeting in memory.

## 6. UI screens and design

Clean dark or light theme, one accent colour, rounded cards, status
chips, smooth card animations, confidence bar and source quote on every
item.

  -----------------------------------------------------------------------
  Screen                              Contents
  ----------------------------------- -----------------------------------
  Dashboard                           Upcoming deadlines, open items,
                                      recent meetings, conflicts awaiting
                                      review

  Meeting Room                        Live transcript with speaker
                                      colours; streaming
                                      Decision/Action/Intent cards; agent
                                      activity

  Review & Confirm                    Items with owner, deadline,
                                      confidence, source quote;
                                      Approve/Edit/Reject/Approve all

  Conflict View                       Current vs earlier decision,
                                      speaker, quote and explanation;
                                      Keep new/Keep old/Merge

  Decision Memory                     Searchable timeline by topic

  Person Profile                      Open tasks, on-time rate, average
                                      slip, reliability score

  Weekly Digest                       Per-person email/Telegram preview
  -----------------------------------------------------------------------

Hinglish UI examples: "Soft commitment detected: dekhte hain"; "parso →
Mon, 3 Nov".

## 7. Postgres data model

-   `members` (id, name, aliases\[\], telegram_id, email)
-   `meetings` (id, title, date, attendees\[\], raw_transcript)
-   `segments` (id, meeting_id, speaker, text, ts)
-   `items` (id, meeting_id, type \[decision/action/intent\], text,
    owner_id, deadline, confidence, source_quote, status
    \[pending/approved/rejected/done\], tracker_ref)
-   `decisions` (id, topic, statement, embedding, meeting_id,
    supersedes_id, status)
-   `conflicts` (id, new_item_id, old_decision_id, label, explanation,
    resolution)
-   `reminders` (id, item_id, send_at, channel, sent)
-   `commitment_stats` (member_id, total, on_time, avg_slip_days)

## 8. Eight-hour build plan

  -----------------------------------------------------------------------
  Time                    Goal                    Deliverables
  ----------------------- ----------------------- -----------------------
  0:00--1:00              Foundation              Repo, Next.js +
                                                  Tailwind, Supabase
                                                  schema, env keys, first
                                                  Vercel deploy, team
                                                  roster, three demo
                                                  transcripts

  1:00--2:30              Core agents             Extractor JSON schema,
                                                  Hinglish Resolver,
                                                  Critic; test all three
                                                  transcripts

  2:30--4:00              Memory + conflicts      Decision ledger,
                                                  embeddings, Memory
                                                  Agent, Conflict Agent;
                                                  Meeting 3 flags Meeting
                                                  1

  4:00--5:30              UI core                 Dashboard, live replay
                                                  Meeting Room, Review &
                                                  Confirm, Conflict View

  5:30--6:30              Execution               Tracker integration
                                                  after approval,
                                                  Telegram bot, scheduled
                                                  reminders

  6:30--7:15              Digest + score          Weekly email digest,
                                                  reliability warning,
                                                  person profile

  7:15--7:45              Polish + deploy         Loading states, error
                                                  fallbacks, production
                                                  test, backup demo video

  7:45--8:00              Pitch                   Three-minute demo,
                                                  README, architecture
                                                  slide
  -----------------------------------------------------------------------

Original cut order: audio upload, person profile, Telegram, digest,
reliability score. Never cut extraction, Hinglish resolution, conflict
detection, confirmation or one real tracker task.

## 9. Demo concept and pitch flow

Meeting 1 (12 Oct): vendor payment installments and launch date. Meeting
2 (19 Oct): progress, a soft "dekhte hain" intent and slipped task.
Meeting 3 (26 Oct): payment moved to next month's end due to cash flow,
contradicting Meeting 1; launch date updated; further tasks and
reliability warning.

Three-minute pitch: problem; run Meeting 3; show conflict against
Meeting 1; approve an item and show real tracker task plus Telegram
confirmation; show reliability warning and digest; mention roadmap.

## 10. Mapping to brief

  -----------------------------------------------------------------------
  Required capability                 Yaad implementation
  ----------------------------------- -----------------------------------
  Transcript ingestion with speaker   Labelled transcripts, live
  attribution                         replay/upload/audio modes

  Decisions, actions, owners,         Extractor + Hinglish Resolver
  deadlines                           

  Earlier-decision conflicts          Decision ledger + Conflict Agent

  Tracker tasks                       Action Agent + Trello/GitHub

  Deadline reminders                  Scheduled Telegram job

  Weekly per-person digest            Digest Agent + email

  Confirmation before posting         Review & Confirm
  -----------------------------------------------------------------------

## 11. Risks and fallbacks

-   Invalid LLM JSON: schema validation and one automatic retry.
-   Missed conflict: pre-test exact transcripts and keep seeded fallback
    decision.
-   API/network failure: backup demo video and cached outputs.
-   Integration auth failure: configure tokens early.
-   Over-scoping: use the stated cut order.
-   Hallucinated tasks: Critic Agent and mandatory source quotes.

## 12. Judging messages

"We didn't build a summariser. We built an agent team with a verifier
and a decision ledger." "Every extracted item is traceable to a quote,
and nothing posts without human confirmation." "It understands how India
actually talks in meetings." "The longer a team uses it, the smarter the
reliability score gets."

## 13. Final tightening rules

1.  All outgoing tasks, Telegram messages, reminders and digests require
    approval.
2.  Audio speaker attribution requires a Review mapping step
    (e.g. Speaker 1 → Rahul); labelled transcripts skip it.
3.  Reminders fire 24 hours and 2 hours before deadlines; Demo Mode can
    set a deadline 2 minutes ahead.
4.  Tracker card must open live in Trello or GitHub; no mockups.
5.  Prioritise memory and conflicts; write the three demo meetings
    first.

## 14. Acceptance tests

1.  Upload labelled transcript; every extracted item shows speaker and
    source quote.
2.  Meeting 1 actions have owner and deadline; relative dates resolve
    against meeting date.
3.  Meeting 3 is flagged against Meeting 1 with explanation, both quotes
    and dates.
4.  After approval, a real tracker card/issue appears with owner, due
    date and meeting link.
5.  Demo Mode Telegram reminder arrives within two minutes.
6.  Two different people receive different weekly digests.
7.  With no approval, tracker and Telegram show zero new activity;
    rejected item is removed.

## 15. Demo language

Hinglish is recommended as the main demo language; follow it with a
short English meeting. Hindi and other Indian languages are
roadmap/optional choices and should only be demoed after testing. Judges
unfamiliar with Hinglish may need subtitles or English date labels.

## 16. Final deliverables

-   Deployed app URL and Supabase project.
-   GitHub repository with README, architecture diagram and setup.
-   Three demo transcripts.
-   Real tracker board and Telegram bot.
-   Backup demo video (2--3 minutes).
-   Rehearsed three-minute pitch.

## 17. Demo transcripts

### Meeting 1 --- Mon 12 Oct 2026 (Hinglish)

Priya: Theek hai, shuru karte hain. Sabse pehle vendor payment. Rahul,
status?\
Rahul: Invoice aa gaya hai, 2.4 lakh ka. Do installment mein dena hai.\
Priya: Toh decide karte hain, pehla installment hum 15 tareekh ko clear
karenge, aur doosra installment 30 tareekh ko. Rahul ye dekh lega.\
Rahul: Done, 15 ko pehla ho jayega.\
Priya: Ab launch date. Amit, kitna time lagega?\
Amit: Build ready hone mein do hafte lagenge.\
Priya: Final, launch 30 November ko hoga. Amit, staging build is Friday
tak de dena.\
Amit: Theek hai, Friday tak.\
Neha: Mujhe landing page copy chahiye, main parso tak draft share kar
deti hoon.\
Priya: Haan Neha, parso tak draft share kar do. Aur ads ka kya?\
Neha: Ads ke baare mein dekhte hain, abhi budget clear nahi hai.\
Priya: Okay, wo baad mein.

### Meeting 2 --- Mon 19 Oct 2026 (Hinglish)

Priya: Updates lete hain. Amit, staging?\
Amit: Do din late hai, kal tak de dunga.\
Rahul: Pehla installment 15 ko ho gaya tha.\
Priya: Good. Rahul, vendor ke contract renewal ke docs Thursday tak bhej
dena.\
Rahul: Ji, Thursday tak bhej dunga.\
Neha: Landing page ka feedback aa gaya hai, final version agle Monday
tak ready kar dungi.\
Priya: Ads wala kya hua?\
Neha: Dekhte hain, ho jayega.\
Priya: Ek decision: har Friday shaam 5 baje weekly demo hoga, sabko
attend karna hai.

### Meeting 3 --- Mon 26 Oct 2026 (Hinglish)

Priya: Chalo shuru karte hain. Rahul, doosre installment ka kya scene
hai?\
Rahul: 30 tareekh ko due hai, par cash flow thoda tight hai.\
Priya: Theek hai, payment agle mahine ke end mein karte hain. Rahul,
vendor ko bata dena.\
Rahul: Ji. Contract renewal docs abhi pending hain, sorry.\
Priya: Koi baat nahi, kal tak bhej do.\
Rahul: Ho jayega.\
Amit: Staging live hai. Production deploy parso tak kar dunga.\
Priya: Ek aur cheez, QA ke liye time chahiye, toh launch 30 November se
hata ke 7 December kar dete hain.\
Neha: Press note ke baare mein dekhte hain agle hafte.

### Meeting E1 --- Tue 27 Oct 2026 (English)

Priya: Quick sync. First, the weekly demo. Fridays at 5 are clashing
with other commitments, so let's move the demo to Thursdays at 4 pm.\
Amit: Works for me. The login bug is still open. I'll fix it by end of
day tomorrow.\
Neha: I'll send the press note draft by next Wednesday.\
Priya: Good. Also, we won't run any paid ads until after the launch.\
Rahul: Maybe we should look at a second vendor as backup. I'll think
about it.\
Priya: Fine, let's revisit that later.

## 18. Expected extraction --- ground truth

  --------------------------------------------------------------------------------
  Meeting     Item          Type         Owner       Resolved    Notes
                                                     deadline    
  ----------- ------------- ------------ ----------- ----------- -----------------
  M1          Vendor        Decision +   Rahul       Thu 15 Oct  Completed per M2
              installment 1 action                               

  M1          Vendor        Decision +   Rahul       Fri 30 Oct  Later
              installment 2 action                               contradicted in
                                                                 M3

  M1          Launch date   Decision     Priya       Mon 30 Nov  Later updated in
                                                                 M3

  M1          Staging build Action       Amit        Fri 16 Oct  "is Friday tak"

  M1          Landing page  Action       Neha        Wed 14 Oct  "parso"
              draft                                              

  M1          Ads           Intent only  Neha        None        "dekhte hain"
                                                                 must not become a
                                                                 decision

  M2          Staging build Action       Amit        Tue 20 Oct  "kal tak",
                                                                 slipped from 16
                                                                 Oct

  M2          Contract      Action       Rahul       Thu 22 Oct  Missed, reappears
              renewal docs                                       in M3

  M2          Landing page  Action       Neha        Mon 26 Oct  "agle Monday tak"
              final                                              

  M2          Ads           Intent only  Neha        None        "ho jayega"
                                                                 without a date

  M2          Weekly demo   Decision     Priya       Recurring   Later
              Fridays 5 pm                                       contradicted in
                                                                 E1

  M3          Installment 2 Decision     Rahul       Mon 30 Nov  Conflict with M1
              moved to end                                       (contradiction)
              of next month                                      

  M3          Contract      Action       Rahul       Tue 27 Oct  Reliability
              renewal docs                                       warning: second
                                                                 slip

  M3          Production    Action       Amit        Wed 28 Oct  "parso"
              deploy                                             

  M3          Launch 30 Nov Decision     Priya       Mon 7 Dec   Conflict with M1,
              to 7 Dec                                           labelled update

  M3          Press note    Intent only  Neha        None        "dekhte hain"

  E1          Weekly demo   Decision     Priya       Recurring   Conflict with M2
              to Thursdays                                       
              4 pm                                               

  E1          Fix login bug Action       Amit        Wed 28 Oct  "end of day
                                                                 tomorrow"

  E1          Press note    Action       Neha        Wed 4 Nov   "next Wednesday"
              draft                                              

  E1          No paid ads   Decision     Priya       None        No conflict; ads
              until after                                        were only intent
              launch                                             before

  E1          Second vendor Intent only  Rahul       None        "I'll think about
              as backup                                          it"
  --------------------------------------------------------------------------------

**Pass criteria:** all dates resolve correctly; five intent items are
not tasks; exactly three conflicts fire: M3 vs M1 installment
(contradiction), M3 vs M1 launch (update), E1 vs M2 demo schedule. E1's
ads decision must not raise a false conflict.

## Source fidelity notes

This Markdown is a structured transcription of the supplied PDF. The
PDF's original stack is retained and distinguished from the later
implementation choice. Section 9's short summary says Meeting 3 adds a
task for Rahul; the detailed transcript and expected table identify
contract renewal documents. This inconsistency is retained for explicit
review rather than silently corrected.
