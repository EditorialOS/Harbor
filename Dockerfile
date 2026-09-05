# Harbor control plane production image for Fly Machines.
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY harbor ./harbor
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HARBOR_RUNTIME_WHEEL_DIR=/opt/harbor/wheels
WORKDIR /opt/harbor
COPY --from=build /src/dist/ /opt/harbor/wheels/
RUN set -- /opt/harbor/wheels/*.whl; \
    test "$#" -eq 1 && test -f "$1"; \
    pip install --no-cache-dir "$1[production]"
EXPOSE 8080
CMD ["uvicorn", "harbor.control_plane:app", "--host", "0.0.0.0", "--port", "8080"]
