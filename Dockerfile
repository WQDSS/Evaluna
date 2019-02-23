FROM python:3 as base

RUN mkdir /model
COPY model/w2_exe_linux_par /model/

# use pipenv to install dependencies
RUN pip install pipenv
WORKDIR /app
COPY Pipfile  Pipfile.lock ./

FROM base as base-with-deps
RUN pipenv install --deploy --system

FROM base as base-with-devel-deps
RUN pipenv install -d --system

FROM base-with-deps as release
# expose necessary port
ENV PORT '80'
EXPOSE ${PORT}

# define entrypoint
ENTRYPOINT ["python3",  "src/api.py"]

# copy the model -- temporary hack, should probably receive all inputs from user via request
COPY data/mock_stream_A/* /model/  

# copy the contents of the app
COPY dss/src/ /app/src/

FROM base-with-devel-deps as test
# copy the contents of the app
COPY dss/src/ /app/src/

ENV PYTHONPATH=/app/src
COPY dss/test/ /test/

# ignore collections warning about deprecation warning, there's nothing we can do about that for now
ENTRYPOINT [ "pytest", "/test", "-W", "ignore::DeprecationWarning" ]

FROM release
