#! /bin/bash -e
bump_type=""
if [ "$1" == "bump" ] ; then
    bump_type="patch"
    if [ -n "$2" ] ; then
        bump_type="$2"
    fi
fi

current_commit=$(git rev-parse --short HEAD)
image_tag=${TAG:-$current_commit}
docker build --rm -f "Dockerfile" -t waterqualitydss:latest -t "booooh/waterqualitydss:$image_tag" .
docker push "booooh/waterqualitydss:$image_tag"

# update Chart.yaml
if  [ -n "$bump_type" ] ; then

    # update the appVersion in the chart, and the chart version (by default, a patch-level bump)
    python dss/scripts/update_chart_version.py --bump_part "$bump_type" --app_version "${image_tag}"
fi

