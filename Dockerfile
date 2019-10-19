FROM python:3 as base

# setup the directory structure for models and the executables
RUN mkdir /models
RUN mkdir /dss-bin
COPY model/linux_model_64_v4_1 /dss-bin/w2_exe_linux_par

ENV  WQDSS_MODEL_EXE "/dss-bin/w2_exe_linux_par"
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

# copy the model as the default model
COPY data/mock_stream_A/* /models/default/
COPY data/yarqon/* /models/yarqon/

# copy the contents of the app
COPY dss/src/ /app/src/
RUN ln -s /app/src/static /app/static

FROM base-with-devel-deps as test
# copy the contents of the app
COPY data/mock_stream_A/* /test/mock_stream_A/
COPY dss/src/ /app/src/

ENV PYTHONPATH=/app/src
COPY dss/test/ /test/

ENTRYPOINT ["/test/run_tests.sh"]

CMD ["/test/"]

FROM release
