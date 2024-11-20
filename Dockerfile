ARG VIRTUAL_ENV=/app/.venv
FROM python:3.12.7 AS build
ARG VIRTUAL_ENV
WORKDIR /app

COPY requirements-poetry.txt .
RUN pip install --no-cache-dir -r requirements-poetry.txt

RUN python -m venv $VIRTUAL_ENV
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-cache
COPY . .

# To be able to use all venv packages, we use /app/.venv/bin/python as entrypoint. But that file is a symlink to
# /usr/local/bin/python (in the official python:... image). However, the ubuntu/python image we use at run-time does
# not have the Python binary at this path, but instead it resides at /usr/bin/python3. We therefore remove the symlink
# and create a new one to the correct Python path.
# Note: we do this already here at the build stage because we don't have a shell or tools (like "ln") in the run-time
# stage.
RUN rm .venv/bin/python && ln -s /usr/bin/python3 .venv/bin/python

# Use the Ubuntu chiseled minimal Docker image for Python. In contrast to Google's "distroless" Python image, which
# offers no control over the Python version (other than "Python 3"), the Ubuntu image offers at least control of
# the minor version of Python (e.g. "3.12"). I'm not aware of free(!) minimal images that offer patch-level control.
FROM ubuntu/python:3.12-24.04 AS backend
# Remove the Pebble manager which we don't need and which may contain vulnerabilities found by scanners
# (which is annoying, even if the findings are false positives). To be able to delete them, we need a shell and root
# temporarily ...
COPY --from=busybox:uclibc /bin/sh /bin/sh
COPY --from=busybox:uclibc /bin/rm /bin/rm
USER 0
RUN rm /usr/bin/pebble
RUN rm /bin/sh
USER _daemon_
ENV PYTHONUNBUFFERED=1
ENV TZ="UTC"
WORKDIR /app
EXPOSE 8000
COPY --from=build /app /app
ENTRYPOINT ["/app/.venv/bin/uvicorn"]
CMD ["main:app", "--host", "0.0.0.0", "--port", "8000"]
