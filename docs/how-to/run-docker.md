# Run with Docker

The repo provides a Dockerfile to build a runtime image that runs the `dqf` console script.

Build

```
docker build -t dqf:latest .
```

Run (mount configs and provide env)

```
docker run --rm \
  -e SRC_URI="postgres://user:pass@host:5432/db" \
  -e TGT_URI="bigquery://" \
  -e GCHAT_DQ_WEBHOOK="https://chat.googleapis.com/..." \
  -v $PWD/config:/app/config \
  dqf:latest --config-file hello_world --filetype yaml --vars env=prod run_label=nightly
```

Notes

- ENTRYPOINT is `dqf` (see Dockerfile). Pass CLI arguments after the image name.
- Provide connector credentials via env vars referenced by your config’s `connections.*_env_var`.
- For Oracle thick mode or custom drivers, extend the image to add OS libraries.

