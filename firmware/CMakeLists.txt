# Adapted from ESP-IDF v6.1 examples/get-started/hello_world.
cmake_minimum_required(VERSION 3.22)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(voice_device)

