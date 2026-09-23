set(Namespace_SRCS
        freecad/ORfemn/__init__.py
        freecad/ORfemn/init_gui.py
        freecad/ORfemn/version.py
        freecad/ORfemn/kfile_format.py
        freecad/ORfemn/radioss_runner.py
        freecad/ORfemn/templates.json
        freecad/ORfemn/keywords_with_parameters.json
        freecad/ORfemn/keywords_clean.json
        freecad/ORfemn/commands/__init__.py
        freecad/ORfemn/commands/create_basic_k_file.py
        freecad/ORfemn/commands/create_radioss_model.py
        freecad/ORfemn/commands/export_radioss_input.py
        freecad/ORfemn/commands/keyword_editor_command.py
        freecad/ORfemn/commands/open_cache_viewer.py
        freecad/ORfemn/commands/template_editor_command.py
        freecad/ORfemn/commands/run_solver_command.py
        freecad/ORfemn/gui/__init__.py
        freecad/ORfemn/gui/cache_viewer.py
        freecad/ORfemn/gui/keyword_editor.py
        freecad/ORfemn/gui/template_editor.py
        freecad/ORfemn/gui/run_dialog.py
        freecad/ORfemn/resources/icons/ORfemn-icon.svg
        freecad/ORfemn/resources/icons/create_model.svg
        freecad/ORfemn/resources/icons/create_k_file.svg
        freecad/ORfemn/resources/icons/export.svg
        freecad/ORfemn/resources/icons/import.svg
        freecad/ORfemn/resources/icons/keyword_editor.svg
        freecad/ORfemn/resources/icons/template_editor.svg
        freecad/ORfemn/resources/icons/run.svg
        freecad/ORfemn/resources/translations/ORfemn_es-ES.ts
)

SOURCE_GROUP("" FILES ${Namespace_SRCS})

ADD_CUSTOM_TARGET(ORFEMN ALL
        SOURCES ${Namespace_SRCS}
)

fc_copy_sources(ORFEMN "${CMAKE_BINARY_DIR}/Mod/ORfe" ${Namespace_SRCS})

foreach(SRC ${Namespace_SRCS})
    get_filename_component(SRC_DIR ${SRC} DIRECTORY)
    INSTALL(FILES ${SRC} DESTINATION Mod/ORfe/${SRC_DIR})
endforeach()
