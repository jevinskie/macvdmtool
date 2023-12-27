cmake_minimum_required(VERSION 3.28)

project(macvdmtool)

set(CMAKE_OSX_ARCHITECTURES "x86_64;arm64")
set(CMAKE_CXX_COMPILER "clang++")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -stdlib=libc++ -v")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -stdlib=libc++ -lc++abi")

include_directories(include)

add_executable(macvdmtool src/main.cpp)

set_property(TARGET macvdmtool PROPERTY CXX_STANDARD 14)

target_link_libraries(macvdmtool "-framework CoreFoundation")
target_link_libraries(macvdmtool "-framework IOKit")


install(TARGETS macvdmtool)