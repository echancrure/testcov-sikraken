#include "Includes.hpp"

#ifndef LABELER_FRONTEND_ACTION_FACTORY_HPP
#define LABELER_FRONTEND_ACTION_FACTORY_HPP

std::unique_ptr<FrontendActionFactory> newLabelerFrontendActionFactory(std::string options);

#endif