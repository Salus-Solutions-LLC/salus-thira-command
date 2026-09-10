# SalCAPA Safe Audio and Video Transcription Design

**Status:** Approved design for the next bounded Issue #131 increment  
**Date:** 09 September 2026  
**Applies after:** SalCAPA v3.104  
**Parent requirements:** [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131) and [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128)

## Decision

The next processing increment will add a local, request-driven worker that prepares English spoken-word transcripts from a narrow set of governed audio and video source records. The worker will extract one approved audio stream, normalize it to a fixed waveform, and run a pinned offline speech-recognition model. A video source is treated only as a container for its audio stream; video frames are not decoded or interpreted.

The first implementation will accept only:

- uncompressed PCM WAV audio;
- MP3 audio with one approved MPEG audio stream; and
- MP4 video with exactly one approved AAC audio stream.

The implementation candidate will use exactly pinned, dependency-audited components:

- FFmpeg and ffprobe for bounded container inspection and audio decoding;
- whisper.cpp for local CPU speech recognition; and
- the English-only Whisper `tiny.en` model, supplied before service startup and verified by exact SHA-256.

Dependency versions, compile options, model source, license records, and hashes must be fixed and rechecked when implementation begins. No executable or model will be downloaded, updated, selected, or replaced during a request. The design is informed by the following primary documentation:

- [FFmpeg protocols and protocol allowlisting](https://ffmpeg.org/ffmpeg-protocols.html)
- [ffprobe media inspection](https://ffmpeg.org/ffprobe.html)
- [whisper.cpp build, input, model, and memory guidance](https://github.com/ggml-org/whisper.cpp)
- [OpenAI Whisper model card and limitations](https://github.com/openai/whisper/blob/main/model-card.md)

## Human and operational purpose

Salus personnel need a practical way to find and review spoken information in governed interviews, briefings, meetings, exercise recordings, incident recordings, voice notes, and similar material without manually replaying every minute. The worker prepares a review aid. It does not listen as a person, determine what happened, decide who spoke, establish consent, qualify intelligence, authenticate a recording, or make a finding.

The user-facing lifecycle is:

`Original recording → separate transcript review aid → Awaiting Human Review → Human Reviewed or Rejected`

An authorized person compares the proposed transcript with the original recording, corrects or rejects it, and decides whether any source information is relevant to research, assessment, planning, operations, commercial work, or PROVE assurance. Review confirms only that the derived representation is usable for source review. It does not establish source authenticity, completeness, custody, speaker identity, truth, evidentiary value, current applicability, or decision authority.

## Included source material

The first worker will accept only a source that satisfies all of the following:

- approved extension, media type, container signature, and detected container agree;
- the source-stored SHA-256 still matches the governed source record;
- WAV contains one PCM signed 16-bit little-endian audio stream at an approved sample rate and channel count;
- MP3 contains one approved MPEG Layer III audio stream and no other stream;
- MP4 contains exactly one approved AAC audio stream and at most one video stream;
- the source has no subtitle, data, attachment, album-art, alternate-audio, playlist, manifest, chapter-action, encrypted, or external-reference stream;
- duration, stream count, sample rate, channel count, stored bytes, probe output, processing time, memory, and derived output remain within server-controlled limits.

The source remains unchanged. The worker may prepare:

- detected container and codec facts;
- duration as reported by the approved stream and container, including any bounded discrepancy;
- source sample rate, channel count, bit rate when safely reported, and selected stream index;
- a temporary mono 16 kHz, signed 16-bit PCM waveform for transcription;
- time-segmented English transcript text;
- bounded recognition-quality and no-speech facts needed to direct human review; and
- exact processing and model provenance.

Container titles, comments, artist names, device strings, embedded artwork, chapters, and arbitrary tags are not copied into the ordinary transcript derivative. A separately approved metadata worker would be required before such fields may become governed searchable information.

## Transcription boundaries and uncertainty

Speech recognition converts audio patterns into proposed words. It can omit speech, invent text during silence or noise, confuse speakers, names, numbers, acronyms, addresses, dates, prices, commands, and technical terms, and place inaccurate timestamps. Performance varies with language, accent, microphone quality, compression, overlapping speech, background noise, distance, and domain vocabulary.

The worker must therefore:

- label every transcript **Speech recognition — Derived and Unverified**;
- keep the derivative **Awaiting Human Review** until an authorized reviewer acts;
- preserve a reference to the exact source and source SHA-256;
- label time segments **Approximate source time** rather than verified event time;
- identify no-speech, low-audibility, clipped, overlapping, and uncertain segments when supported by bounded processing facts;
- avoid an unsupported overall accuracy, truth, confidence, risk, credibility, or speaker score;
- state that punctuation, capitalization, paragraphing, and segment boundaries are proposed formatting;
- never assign a person's name, role, organization, or identity to a voice;
- never treat repeated or clear speech as corroboration;
- never silently translate, summarize, correct, complete, classify, or infer meaning from recognized words; and
- take a search result back to the original recording, approximate time segment, and review state.

The fixed English-only model may produce plausible English text from non-English speech, music, silence, noise, or distorted audio. Suspected unsupported language is therefore labeled **Language Not Reliably Supported — Human Review Needed**; it is not automatically translated or retried with another model.

## Privacy, authority, and disclosure controls

Recordings can contain personal, protected, confidential, privileged, investigative, commercial, health, facility, and operational information. Transcription can make information substantially easier to search and disclose, so the transcript inherits the source tenant and at least the source sensitivity.

- The worker does not determine whether a recording was lawfully made or whether consent, notice, privilege, labor, employment, records, or retention requirements were satisfied.
- The requesting person must supply a legitimate governed purpose and already have authority to access and process the source.
- Transcripts are not used to train, fine-tune, adapt, or evaluate a shared model.
- Source audio, normalized audio, tokens, or transcript text cannot cross a Protected Member or Salus-internal boundary.
- Protected Member views cannot reveal Salus-internal material, another member's material, model diagnostics, or processing details outside the approved disclosure scope.
- An unreviewed transcript cannot establish an allegation, observation, indicator, concern, hypothesis, inference, qualified finding, threat judgment, personnel conclusion, price, cost, legal authority, policy, or operational direction.
- Disclosure requires a governed approved record and authorized human action; the transcript by itself cannot authorize release.
- Correction, supersession, retention, legal hold, deletion, and disclosure decisions remain governed actions and never rewrite the immutable historical source or prior transcript.

## Explicit exclusions

The first worker will reject or defer:

- OGG, Opus, FLAC, AAC files outside MP4, M4A, MOV, AVI, MKV, WebM, MPEG-TS, AMR, WMA, AIFF, RealMedia, playlists, live streams, remote media, and all other unapproved formats;
- variable or malformed WAV structures, non-PCM WAV codecs, unsupported PCM widths or endianness, and repair-dependent containers;
- encrypted, password-protected, DRM-controlled, truncated, malformed, oversized, indefinite-duration, fragmented-reference, or growing files;
- multiple audio streams, audio descriptions, commentary tracks, embedded cover art, attachments, subtitles, closed captions, data streams, and external references;
- video-frame decoding, thumbnails, image extraction, scene analysis, facial or biometric analysis, lip reading, object or activity classification, or visual OCR;
- speaker diarization, speaker recognition, speaker verification, voiceprints, identity matching, or role assignment;
- emotion, sentiment, stress, deception, intoxication, health, demographic, behavioral, credibility, intent, risk, threat, or personality inference;
- sound-event, weapon, alarm, vehicle, location, music, background-conversation, or environment classification;
- language identification, non-English recognition, translation, subtitle production, live captioning, or real-time monitoring;
- meeting attendance, consent, authorship, custody, authenticity, manipulation, deepfake, or evidentiary certification;
- automatic summarization, entity extraction, date or location resolution, relationship analysis, allegation creation, intelligence qualification, finding creation, plan approval, tasking, notification, disclosure, or billing; and
- client-supplied vocabulary, prompts, initial text, model, decoder, executable, stream selection, language, temperature, thresholds, or processing options.

Unsupported material remains immutable and available to authorized personnel for manual review or a later approved worker.

## Probe and decode boundary

Media probing and decoding will not run inside the web process. The orchestration layer starts fixed child-process entry points without a shell and with a minimal environment. Every worker has no network access, a read-only application and model filesystem, an empty private temporary directory, and operating-system resource limits.

Before transcription, the media worker must:

1. verify the approved extension, media type, file signature, and source hash;
2. invoke an exact ffprobe binary with a fixed argument list, bounded JSON output, and a protocol allowlist containing only `file` and `pipe`;
3. validate the probe schema, container, duration, stream count, stream types, codec, sample rate, channels, disposition, and absence of forbidden streams or references;
4. reject more than one audio stream rather than making a discretionary selection;
5. invoke an exact FFmpeg binary with a fixed input demuxer, explicit mapping of the validated audio stream, `-vn`, `-sn`, and `-dn`, and a protocol allowlist containing only `file` and `pipe`;
6. decode to a clean temporary mono 16 kHz signed 16-bit little-endian PCM WAV with no copied metadata, chapters, artwork, attachments, subtitles, or video frames;
7. validate the normalized WAV structure, duration, sample count, channel count, sample rate, byte size, and SHA-256; and
8. remove all temporary material after success or failure.

The production FFmpeg build must disable network, device, and unnecessary protocol support where practical and record its exact version and build configuration. Runtime protocol allowlisting is mandatory even when the build is narrowed. No concat, data, crypto, HTTP, FTP, TCP, UDP, RTSP, pipe-to-executable, device-capture, or user-supplied URL is permitted.

Initial implementation limits will be conservative and server controlled:

- maximum stored source size: 128 MiB;
- maximum duration: 60 minutes;
- maximum streams: two total and one audio stream;
- maximum source audio channels: two;
- maximum source sample rate: 96 kHz;
- normalized waveform: mono, 16 kHz, signed 16-bit little-endian PCM;
- maximum normalized waveform bytes: 120 MiB;
- maximum ffprobe JSON: 256 KiB;
- maximum transcript characters: 500,000;
- maximum transcript segments: 20,000;
- maximum combined worker output: 8 MiB;
- maximum probe wall time: 10 seconds;
- maximum decode wall time: 120 seconds;
- maximum transcription wall time: 20 minutes;
- maximum media-worker address space: 768 MiB;
- maximum transcription-worker address space: 768 MiB;
- maximum open files per worker: 64; and
- thread count, decoder allowlist, model, language, sampling strategy, timestamp mode, and all limits selected by the server.

The implementation may lower these limits to fit the approved low-cost container. Raising a limit, accepting another codec or container, or enabling another processing feature requires a reviewed change and fresh gates. A resource-limit failure is not retried with weaker controls.

## Speech-recognition execution boundary

The transcription worker receives only the validated normalized waveform, never the original media container. It invokes an exact whisper.cpp binary directly without a shell. The binary, its build configuration, the `tiny.en` model, and model SHA-256 are fixed by the release candidate.

The model must be supplied before the service becomes available. Startup or processing verifies the model hash against the release manifest. A missing, writable, unexpected, or mismatched model makes transcription **Unavailable — Manual Review Remains Available**. SalCAPA must not download a model, select a substitute, send the source to an external service, or relax verification.

The invocation uses fixed English transcription, deterministic decoding settings where supported, bounded approximate timestamps, a fixed thread count, no translation, no language detection, no prompts, and no client-selected options. Output is parsed against an allowlisted schema with UTF-8, segment-count, timestamp-order, duration, text-length, and total-size validation.

The worker must not:

- load a model, vocabulary, prompt, configuration, plugin, library, or executable from tenant-controlled or writable storage;
- read user home-directory state or write outside its private temporary directory;
- make a network request or invoke another executable;
- retain normalized audio after the governed job completes;
- expose raw token probabilities as truth or decision confidence;
- infer a speaker, language, emotion, event, classification, or conclusion; or
- reuse source material for training, tuning, shared analytics, or cross-tenant learning.

## Derived records and provenance

One successful job creates an **Audio Transcript Review Aid** or **Video Audio-Track Transcript Review Aid** derivative through the existing transactional processing contract. It records:

- tenant, source material, processing purpose, and requesting authorized actor;
- exact source, normalized-waveform, and transcript SHA-256 values;
- source extension, media type, detected container, selected audio stream, codec, duration, sample rate, channels, and bounded discrepancy facts;
- exact SalCAPA worker, ffprobe, FFmpeg, whisper.cpp, and model versions, build identities, and hashes;
- fixed normalization and transcription settings;
- approximate segment timestamps, character and segment counts, truncation state, no-speech and limitation facts;
- creation date and time in the governed display format;
- uncertainty, privacy, authority, and disclosure limitations; and
- review status, reviewer, corrections, rejection, and supersession lineage.

The normalized waveform is an ephemeral processing artifact. Its hash and transformation facts are retained, but its bytes are removed after successful or failed processing unless a separately authorized preservation requirement is added later. This avoids an unnecessary permanent duplicate of sensitive source audio.

The transcript remains **Derived — Unverified** and **Awaiting Human Review**. An independent reviewer may mark the representation **Human Reviewed** or **Rejected**. Review does not promote source truth, speaker identity, intelligence qualification, evidentiary standing, a finding, threat judgment, plan approval, cost validation, price approval, disclosure authority, legal authority, or operational authority.

A corrected transcript is a new governed derivative linked to the original recording and machine-prepared transcript. Corrections do not overwrite either record. A later source version creates new processing lineage and cannot rewrite a historical derivative or the source basis of an approved record.

## Failure behavior and graceful degradation

No derivative is created unless the orchestration layer validates source integrity, type, probe output, stream selection, decoder identity, normalized waveform, recognizer identity, model hash, transcript structure, all limits, and the final derivative hash.

A signature, format, probe, decode, model, transcription, malformed-output, timeout, memory, version, integrity, or output-limit failure:

- leaves the original bytes and source hash unchanged;
- returns the source to **Ready for Processing**;
- creates no partial searchable transcript;
- records one bounded public failure code and a separate non-sensitive audit event;
- removes the normalized waveform and all temporary output;
- does not retry with another stream, codec, model, language, limit, service, or relaxed control; and
- does not initiate disclosure, notification, billing, scope change, intelligence, assessment, planning, investigation, or another workflow.

If FFmpeg, whisper.cpp, or the model is unavailable, authorized personnel retain manual access to the original recording. Search, review, reporting, and other SalCAPA functions continue without the transcript. The application explains that transcription is unavailable and identifies the manual next step without blaming the user.

## Server-controlled and human-authority contract

The client may provide only a legitimate processing purpose. It cannot select the stream, demuxer, decoder, recognizer, model, language, prompt, temperature, sampling strategy, thread count, timestamps, output format, limits, disclosure scope, or review state.

The media and transcription workers perform no database, network, authorization, billing, disclosure, notification, workflow, finding, assessment, planning, or operational side effect. The governed orchestration layer creates the source-linked derivative and audit events transactionally.

Salus personnel retain professional judgment and all qualification, correction, approval, release, disclosure, legal, policy, commercial, investigative, and operational authority.

## Azure and operating-cost posture

The first worker runs locally and only when requested within the existing production-container allocation. It adds no paid Azure speech service, standing worker, queue, background-compute tier, GPU, duplicate permanent audio store, or external transmission.

FFmpeg, whisper.cpp, and the approximately 75 MiB `tiny.en` model increase the production image or deployment artifact size and add bounded CPU and memory demand. The implementation candidate must measure image-size growth, cold start, decode and transcription time, memory, temporary storage, and concurrency behavior before release. Only one media transcription job per application instance will run in the first increment. Requests beyond that local capacity fail safely with **Transcription Capacity Unavailable — Try Later or Review Manually**; they do not trigger paid scale-out.

The model may be included in the immutable production image or supplied from an already approved deployment artifact location before startup. If an Azure Blob delivery path is used, deployment identity, private access, version pinning, SHA-256 verification, egress, availability, and cost must be validated. Request handling never retrieves the model.

If measurements cannot fit the existing low-cost posture, transcription remains unavailable while manual recording review continues. The implementation must not silently provision a paid service or change scaling, networking, identity, storage, or customer charges.

Any future Azure AI Speech, external transcription, GPU, queue, persistent worker, broader model, additional language, live transcription, or third-party service requires a separate cost, identity, privacy, consent, data-location, retention, procurement, security, disclosure, model-governance, and human-authority review.

## Required acceptance evidence

The implementation candidate must prove:

- deterministic reconstruction of FFmpeg, whisper.cpp, and the exact English model from reviewed, pinned sources and hashes;
- successful bounded transcription from fictional demonstration PCM WAV, MP3, and MP4-with-AAC sources;
- no video-frame decode or analysis for an MP4 source;
- exact original-byte and source-hash immutability before and after processing;
- exact source-to-normalized-audio-to-transcript lineage, with normalized bytes removed after processing;
- complete worker, ffprobe, FFmpeg, whisper.cpp, build, model, and settings provenance;
- explicit word, name, number, acronym, punctuation, timing, language, silence, noise, overlap, and audibility uncertainty;
- safe no-speech, non-English, music, silence, noisy, clipped, and overlapping-speech behavior;
- no speaker identification, diarization, biometric work, emotion or credibility inference, sound-event classification, language detection, translation, summarization, or video analysis;
- no client-selected stream, executable, codec, model, prompt, language, setting, threshold, output, or limit;
- no network access, external retrieval, request-time model download, source training, shared analytics, cross-tenant learning, or persistent temporary file;
- mismatch, unsupported format, multiple-audio-stream, forbidden-stream, external-reference, encrypted, DRM, malformed, truncated, excessive-duration, excessive-size, excessive-rate, timeout, memory-limit, invalid-output, binary-version, and model-hash rejection;
- child-process failure isolation and no partial derivative;
- tenant, role, sensitivity, disclosure, purpose, and Protected Member access denial;
- independent representation review without promotion of source truth, speaker identity, evidence, or authority;
- correction and supersession lineage without overwriting the original or prepared transcript;
- rejected derivatives excluded from search and accepted matches linked to source time and review state;
- portable backup verification and disaster-recovery validation for transcript and provenance records;
- SQLite and PostgreSQL 16 operation;
- production-container execution under the unprivileged identity;
- measured production-image size, CPU, memory, temporary storage, cold start, and one-job concurrency behavior;
- exact dependency, source, license, and container pinning; dependency audit; Bandit; repository hygiene; Azure policy and infrastructure validation; and CodeQL; and
- all existing SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, commercial, investigation, emergency-planning, visual, date/time, and frozen-release regressions.

Test recordings must be created as fictional demonstration fixtures during validation or generated deterministically from repository-owned text-to-speech test assets that contain no real person's voice. No confidential, personal, Protected Member, investigation, customer, employee, or licensed third-party recording may be committed to the repository.

## Deferred sequence

After the standalone audio/video transcription worker is frozen and tested, Issue #131 should proceed through separate bounded decisions for:

1. scanned-PDF page rendering and OCR;
2. broader image and media formats and additional languages;
3. map and geospatial metadata;
4. speaker-separated transcripts without identity, only if privacy and accuracy review supports it;
5. entity, date, and location suggestions;
6. duplicate and relationship analysis; and
7. workload routing and broader analyst triage.

Each worker must preserve immutable sources, exact lineage, uncertainty, tenant and sensitivity boundaries, human authority, failure isolation, cost controls, and manual operating capability when processing is unavailable.
