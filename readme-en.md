# androidTestBed
Tool for creating test environments with Android devices

An attempt to debug and make @alvesRenan 's testbed more accessible to open source community 

## First Steps
First, you need to know the version of the API used by the Docker server part:
```
# docker version
```
If you are not using version 1.26, you need to modify the creator.py and manager.py files on lines 12 and 14 respectively (the smallest version supported is 1.21).

Downloading Images:
- Client image download: ```docker pull renanalves/android-testbed```

- Download the server image (new version available): ```docker pull renanalves/server-testbed```

## Using the tool

NOTE: The videos are from an older version of the tool but are still valid.

A video demonstrating the installation can be found at: https://youtu.be/7nu-24ESTl0

In addition to a video demonstrating the running tool: https://youtu.be/uZj6Gl6R19Q

The step by step for using the tool and also how it is structured can be seen at the link below: http://www.repositorio.ufc.br/bitstream/riufc/29546/1/2017_tcc_rabarbosa.pdf

MatrixOperationsKotlin application repository: https://github.com/alvesRenan/KotlinMpOS
