# Open Data catalogue

The script that keeps the
[Open Data catalogue](https://huggingface.co/datasets/Gramscii-IT/open-data-catalogue)
on Hugging Face current: a catalogue of 15,990 open datasets of official
statistics and Italian public finance, from ISTAT, Eurostat, OECD, ILO,
DoveVannoINostriSoldi and Cruscotto Italia, with every dataset's
structure, the words its codes stand for, its documentation notes and
one searchable document per dataset and language. What the catalogue
holds, its format and its licences are described in the dataset's own
README.

The catalogue is harvested by the Open Data plugin of
[Semantic Deterministic Graph](https://github.com/Gramscii-Git/semantic-deterministic-graph),
which reads the six providers at the pace they allow, keeps the result in
its database and refreshes it once a day. This repository holds the one
script that turns such a deployment into the publisher.

The territory codes in the catalogue are the identifiers the shapes of
[Gramscii-Git/boundaries](https://github.com/Gramscii-Git/boundaries)
carry, so a dataset keyed by ISTAT, NUTS or ISO code is drawn on a map
without a lookup step.

## What `update` does

```sh
./update            # ask the providers for what moved, then publish
./update publish    # export and upload what the deployment holds now
```

1. `sync`: re-reads the six providers' listings and marks what is new,
   retired or changed.
2. `structure --patience 90`: reads the structures that moved or never
   arrived; a dataset slower than 90 seconds is left with an error and
   asked again next time, so a handful of slow ones never hold the run.
3. `enrich`: rebuilds the documents whose text moved, in every language
   the deployment serves.
4. `export`: writes the seven tables as one archive under `build/`, with
   its manifest and its SHA-256.
5. Uploads the archive, `manifest.json` and `SHA256SUMS` to the dataset,
   checks that the Hub serves the digest it just computed, and prints the
   pin to set in `plugins/opendata/config.yaml` of Semantic Deterministic
   Graph.

The dataset's README is not rewritten by the script: its counts, its date
and its known gaps are prose, updated by hand after each release.

## Requirements

- A checkout of Semantic Deterministic Graph, installed as its README
  says, with a database that holds the catalogue: `SDG_DIR` names it,
  and the default is the directory beside this one.
- The deployment's own embedder, because the documents are indexed as
  they are rebuilt.
- The `hf` client, logged in to an account that may write to the
  `Gramscii-IT` organisation.

`DRY_RUN=1 ./update publish` writes the archive and uploads nothing.

## Running it every week

`it.gramscii.open-data-catalogue.plist` runs `./update` every Monday at
03:00 on the machine that holds the catalogue, with launchd. Set the two
paths inside it, then:

```sh
cp it.gramscii.open-data-catalogue.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/it.gramscii.open-data-catalogue.plist
```

The log lands where the plist says. A release is complete once the pin
printed at the end is in Semantic Deterministic Graph and the dataset's
README says what changed.

## Licence

The script and the files in this repository are released under the MIT
licence. The catalogue itself carries the licence of every dataset's own
provider, recorded row by row, as the dataset's README explains.
