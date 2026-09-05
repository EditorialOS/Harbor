# Harbor control plane production image for Fly Machines.
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY harbor ./harbor
RUN pip install --no-cache-dir build && python -m build --wheel && cp dist/*.whl /tmp/harbor_runtime.whl

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HARBOR_RUNTIME_WHEEL=/opt/harbor/harbor_runtime.whl
WORKDIR /opt/harbor
COPY --from=build /tmp/harbor_runtime.whl /opt/harbor/harbor_runtime.whl
RUN pip install --no-cache-dir '/opt/harbor/harbor_runtime.whl[production]'
EXPOSE 8080
CMD ["uvicorn", "harbor.control_plane:app", "--host", "0.0.0.0", "--port", "8080"]
