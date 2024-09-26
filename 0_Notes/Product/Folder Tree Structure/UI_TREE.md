```
src
├── @core
│   ├── animations
│   │   └── core.animation.ts
│   ├── common.module.ts
│   ├── components
│   │   ├── card-snippet
│   │   │   ├── card-snippet.component.html
│   │   │   ├── card-snippet.component.scss
│   │   │   ├── card-snippet.component.ts
│   │   │   └── card-snippet.module.ts
│   │   ├── core-card
│   │   │   ├── core-block-ui
│   │   │   │   ├── core-block-ui.component.html
│   │   │   │   ├── core-block-ui.component.scss
│   │   │   │   └── core-block-ui.component.ts
│   │   │   ├── core-card.component.html
│   │   │   ├── core-card.component.ts
│   │   │   └── core-card.module.ts
│   │   ├── core-menu
│   │   │   ├── core-menu.component.html
│   │   │   ├── core-menu.component.scss
│   │   │   ├── core-menu.component.ts
│   │   │   ├── core-menu.module.ts
│   │   │   ├── core-menu.service.ts
│   │   │   ├── horizontal
│   │   │   │   ├── collapsible
│   │   │   │   │   ├── collapsible.component.html
│   │   │   │   │   └── collapsible.component.ts
│   │   │   │   └── item
│   │   │   │       ├── item.component.html
│   │   │   │       └── item.component.ts
│   │   │   └── vertical
│   │   │       ├── collapsible
│   │   │       │   ├── collapsible.component.html
│   │   │       │   ├── collapsible.component.scss
│   │   │       │   └── collapsible.component.ts
│   │   │       ├── item
│   │   │       │   ├── item.component.html
│   │   │       │   ├── item.component.scss
│   │   │       │   └── item.component.ts
│   │   │       └── section
│   │   │           ├── section.component.html
│   │   │           └── section.component.ts
│   │   ├── core-sidebar
│   │   │   ├── core-sidebar.component.html
│   │   │   ├── core-sidebar.component.ts
│   │   │   ├── core-sidebar.module.ts
│   │   │   └── core-sidebar.service.ts
│   │   ├── core-touchspin
│   │   │   ├── core-touchspin.component.html
│   │   │   ├── core-touchspin.component.scss
│   │   │   ├── core-touchspin.component.ts
│   │   │   └── core-touchspin.module.ts
│   │   ├── index.ts
│   │   └── theme-customizer
│   │       ├── theme-customizer.component.html
│   │       ├── theme-customizer.component.scss
│   │       ├── theme-customizer.component.ts
│   │       └── theme-customizer.module.ts
│   ├── core.module.ts
│   ├── directives
│   │   ├── core-feather-icons
│   │   │   └── core-feather-icons.ts
│   │   ├── core-ripple-effect
│   │   │   └── core-ripple-effect.directive.ts
│   │   └── directives.ts
│   ├── lib
│   │   └── flowy
│   │       ├── flowy.js
│   │       ├── index.css
│   │       └── index.js
│   ├── pipes
│   │   ├── diclen.pipe.ts
│   │   ├── filter.pipe.ts
│   │   ├── initials.pipe.ts
│   │   ├── pipes.module.ts
│   │   ├── preserve-order-pipe.pipe.spec.ts
│   │   ├── preserve-order-pipe.pipe.ts
│   │   ├── safe.pipe.ts
│   │   └── stripHtml.pipe.ts
│   ├── scss
│   │   ├── angular
│   │   │   ├── libs
│   │   │   │   ├── blockui.component.scss
│   │   │   │   ├── context-menu.component.scss
│   │   │   │   ├── datatables.component.scss
│   │   │   │   ├── date-time-picker.component.scss
│   │   │   │   ├── drag-drop.component.scss
│   │   │   │   ├── file-uploader.component.scss
│   │   │   │   ├── flatpickr.component.scss
│   │   │   │   ├── form-wizard.component.scss
│   │   │   │   ├── media-player.component.scss
│   │   │   │   ├── noui-slider.component.scss
│   │   │   │   ├── quill-editor.component.scss
│   │   │   │   ├── ratings.component.scss
│   │   │   │   ├── select.component.scss
│   │   │   │   ├── sweet-alerts.component.scss
│   │   │   │   ├── swiper.component.scss
│   │   │   │   ├── toastr.component.scss
│   │   │   │   ├── tour.component.scss
│   │   │   │   └── tree-view.component.scss
│   │   │   ├── ng-bootstrap
│   │   │   │   ├── _accordion.scss
│   │   │   │   ├── _carousel.scss
│   │   │   │   ├── _dropdown.scss
│   │   │   │   ├── _index.scss
│   │   │   │   ├── _list-group.scss
│   │   │   │   ├── _modal.scss
│   │   │   │   └── _progress.scss
│   │   │   ├── overrides.scss
│   │   │   ├── _animation.scss
│   │   │   ├── _dark-layout.scss
│   │   │   ├── _index.scss
│   │   │   └── _misc.scss
│   │   ├── base
│   │   │   ├── bootstrap-extended
│   │   │   │   ├── mixins
│   │   │   │   │   ├── _navs.scss
│   │   │   │   │   └── _type.scss
│   │   │   │   ├── _alert.scss
│   │   │   │   ├── _badge.scss
│   │   │   │   ├── _breadcrumb.scss
│   │   │   │   ├── _button-group.scss
│   │   │   │   ├── _buttons.scss
│   │   │   │   ├── _card.scss
│   │   │   │   ├── _code.scss
│   │   │   │   ├── _collapse.scss
│   │   │   │   ├── _dropdown.scss
│   │   │   │   ├── _forms.scss
│   │   │   │   ├── _functions.scss
│   │   │   │   ├── _helper.scss
│   │   │   │   ├── _include.scss
│   │   │   │   ├── _list-group.scss
│   │   │   │   ├── _media.scss
│   │   │   │   ├── _mixins.scss
│   │   │   │   ├── _modal.scss
│   │   │   │   ├── _nav.scss
│   │   │   │   ├── _navbar.scss
│   │   │   │   ├── _pagination.scss
│   │   │   │   ├── _popover.scss
│   │   │   │   ├── _progress.scss
│   │   │   │   ├── _reboot.scss
│   │   │   │   ├── _tables.scss
│   │   │   │   ├── _toast.scss
│   │   │   │   ├── _type.scss
│   │   │   │   ├── _utilities.scss
│   │   │   │   └── _variables.scss
│   │   │   ├── bootstrap-extended.scss
│   │   │   ├── bootstrap.scss
│   │   │   ├── colors.scss
│   │   │   ├── components
│   │   │   │   ├── avatar.scss
│   │   │   │   ├── bootstrap-social.scss
│   │   │   │   ├── chart.scss
│   │   │   │   ├── customizer.scss
│   │   │   │   ├── demo.scss
│   │   │   │   ├── divider.scss
│   │   │   │   ├── search.scss
│   │   │   │   ├── timeline.scss
│   │   │   │   ├── _include.scss
│   │   │   │   ├── _variables-dark.scss
│   │   │   │   └── _variables.scss
│   │   │   ├── components.scss
│   │   │   ├── core
│   │   │   │   ├── colors
│   │   │   │   │   ├── palette-gradient.scss
│   │   │   │   │   ├── palette-noui.scss
│   │   │   │   │   ├── palette-variables.scss
│   │   │   │   │   └── _palette.scss
│   │   │   │   ├── layouts
│   │   │   │   │   ├── _content.scss
│   │   │   │   │   ├── _footer.scss
│   │   │   │   │   └── _sidebar.scss
│   │   │   │   ├── menu
│   │   │   │   │   ├── menu-types
│   │   │   │   │   │   ├── horizontal-menu.scss
│   │   │   │   │   │   ├── vertical-menu.scss
│   │   │   │   │   │   └── vertical-overlay-menu.scss
│   │   │   │   │   └── _navigation.scss
│   │   │   │   └── mixins
│   │   │   │       ├── alert.scss
│   │   │   │       ├── hex2rgb.scss
│   │   │   │       ├── main-menu-mixin.scss
│   │   │   │       └── transitions.scss
│   │   │   ├── custom-rtl.scss
│   │   │   ├── pages
│   │   │   │   ├── app-calendar.scss
│   │   │   │   ├── app-chat-list.scss
│   │   │   │   ├── app-chat.scss
│   │   │   │   ├── app-ecommerce-details.scss
│   │   │   │   ├── app-ecommerce.scss
│   │   │   │   ├── app-email.scss
│   │   │   │   ├── app-file-manager.scss
│   │   │   │   ├── app-invoice-list.scss
│   │   │   │   ├── app-invoice-print.scss
│   │   │   │   ├── app-invoice.scss
│   │   │   │   ├── app-kanban.scss
│   │   │   │   ├── app-todo.scss
│   │   │   │   ├── app-user.scss
│   │   │   │   ├── dashboard-ecommerce.scss
│   │   │   │   ├── page-auth.scss
│   │   │   │   ├── page-blog.scss
│   │   │   │   ├── page-coming-soon.scss
│   │   │   │   ├── page-faq.scss
│   │   │   │   ├── page-knowledge-base.scss
│   │   │   │   ├── page-misc.scss
│   │   │   │   ├── page-pricing.scss
│   │   │   │   ├── page-profile.scss
│   │   │   │   ├── sla-metrix.scss
│   │   │   │   ├── ui-colors.scss
│   │   │   │   └── ui-feather.scss
│   │   │   ├── plugins
│   │   │   │   ├── charts
│   │   │   │   │   └── chart-apex.scss
│   │   │   │   ├── extensions
│   │   │   │   │   ├── ext-component-context-menu.scss
│   │   │   │   │   ├── ext-component-drag-drop.scss
│   │   │   │   │   ├── ext-component-media-player.scss
│   │   │   │   │   ├── ext-component-ratings.scss
│   │   │   │   │   ├── ext-component-sliders.scss
│   │   │   │   │   ├── ext-component-sweet-alerts.scss
│   │   │   │   │   ├── ext-component-swiper.scss
│   │   │   │   │   ├── ext-component-toastr.scss
│   │   │   │   │   ├── ext-component-tour.scss
│   │   │   │   │   └── ext-component-tree.scss
│   │   │   │   ├── forms
│   │   │   │   │   ├── form-file-uploader.scss
│   │   │   │   │   ├── form-number-input.scss
│   │   │   │   │   ├── form-quill-editor.scss
│   │   │   │   │   ├── form-validation.scss
│   │   │   │   │   ├── form-wizard.scss
│   │   │   │   │   ├── pickers
│   │   │   │   │   │   ├── form-flat-pickr.scss
│   │   │   │   │   │   └── form-pickadate.scss
│   │   │   │   │   └── select2
│   │   │   │   │       └── _select2.scss
│   │   │   │   ├── maps
│   │   │   │   │   └── map-leaflet.scss
│   │   │   │   ├── tables
│   │   │   │   │   ├── table-ag-grid.scss
│   │   │   │   │   └── _datatables.scss
│   │   │   │   └── ui
│   │   │   │       ├── coming-soon.scss
│   │   │   │       └── _breakpoints.scss
│   │   │   └── themes
│   │   │       ├── bordered-layout.scss
│   │   │       ├── dark-layout.scss
│   │   │       ├── fixed-layout.scss
│   │   │       ├── fluent-layout.scss
│   │   │       └── semi-dark-layout.scss
│   │   ├── core.scss
│   │   └── style2.scss
│   ├── services
│   │   ├── common-util.service.spec.ts
│   │   ├── common-util.service.ts
│   │   ├── config.service.ts
│   │   ├── loading-screen.service.ts
│   │   ├── media.service.ts
│   │   └── translation.service.ts
│   └── types
│       ├── core-config.ts
│       ├── core-menu.ts
│       └── index.ts
├── app
│   ├── admin
│   │   ├── admin-routing.module.ts
│   │   ├── admin.module.ts
│   │   ├── components
│   │   │   ├── add-login-details-sidebar
│   │   │   │   ├── add-login-details-sidebar.component.html
│   │   │   │   ├── add-login-details-sidebar.component.scss
│   │   │   │   ├── add-login-details-sidebar.component.spec.ts
│   │   │   │   └── add-login-details-sidebar.component.ts
│   │   │   ├── admin-dashboard
│   │   │   │   ├── admin-dashboard.component.html
│   │   │   │   ├── admin-dashboard.component.scss
│   │   │   │   ├── admin-dashboard.component.spec.ts
│   │   │   │   └── admin-dashboard.component.ts
│   │   │   ├── admin-login
│   │   │   │   ├── admin-login.component.html
│   │   │   │   ├── admin-login.component.scss
│   │   │   │   ├── admin-login.component.spec.ts
│   │   │   │   └── admin-login.component.ts
│   │   │   ├── admin-skeleton
│   │   │   │   ├── admin-skeleton.component.html
│   │   │   │   ├── admin-skeleton.component.scss
│   │   │   │   ├── admin-skeleton.component.spec.ts
│   │   │   │   └── admin-skeleton.component.ts
│   │   │   ├── animated-counter
│   │   │   │   ├── animated-counter.component.html
│   │   │   │   ├── animated-counter.component.scss
│   │   │   │   ├── animated-counter.component.spec.ts
│   │   │   │   └── animated-counter.component.ts
│   │   │   ├── congratulations
│   │   │   │   ├── congratulations.component.html
│   │   │   │   ├── congratulations.component.scss
│   │   │   │   ├── congratulations.component.spec.ts
│   │   │   │   └── congratulations.component.ts
│   │   │   ├── dashboard-instance
│   │   │   │   ├── dashboard-instance.component.html
│   │   │   │   ├── dashboard-instance.component.scss
│   │   │   │   ├── dashboard-instance.component.spec.ts
│   │   │   │   └── dashboard-instance.component.ts
│   │   │   ├── dashboard-instance-invoices
│   │   │   │   ├── dashboard-instance-invoices.component.html
│   │   │   │   ├── dashboard-instance-invoices.component.scss
│   │   │   │   ├── dashboard-instance-invoices.component.spec.ts
│   │   │   │   └── dashboard-instance-invoices.component.ts
│   │   │   ├── dashboard-instance-products
│   │   │   │   ├── dashboard-instance-products.component.html
│   │   │   │   ├── dashboard-instance-products.component.scss
│   │   │   │   ├── dashboard-instance-products.component.spec.ts
│   │   │   │   └── dashboard-instance-products.component.ts
│   │   │   ├── dashboard-instance-security
│   │   │   │   ├── dashboard-instance-security.component.html
│   │   │   │   ├── dashboard-instance-security.component.scss
│   │   │   │   ├── dashboard-instance-security.component.spec.ts
│   │   │   │   └── dashboard-instance-security.component.ts
│   │   │   ├── dashboard-instance-settings
│   │   │   │   ├── dashboard-instance-settings.component.html
│   │   │   │   ├── dashboard-instance-settings.component.scss
│   │   │   │   ├── dashboard-instance-settings.component.spec.ts
│   │   │   │   └── dashboard-instance-settings.component.ts
│   │   │   ├── edit-admin-user
│   │   │   │   ├── edit-admin-user.component.html
│   │   │   │   ├── edit-admin-user.component.scss
│   │   │   │   ├── edit-admin-user.component.spec.ts
│   │   │   │   └── edit-admin-user.component.ts
│   │   │   ├── features-skeleton
│   │   │   │   ├── features-skeleton.component.html
│   │   │   │   ├── features-skeleton.component.scss
│   │   │   │   ├── features-skeleton.component.spec.ts
│   │   │   │   └── features-skeleton.component.ts
│   │   │   ├── get-in-touch
│   │   │   │   ├── get-in-touch.component.html
│   │   │   │   ├── get-in-touch.component.scss
│   │   │   │   ├── get-in-touch.component.spec.ts
│   │   │   │   └── get-in-touch.component.ts
│   │   │   ├── history
│   │   │   │   ├── history.component.html
│   │   │   │   ├── history.component.scss
│   │   │   │   ├── history.component.spec.ts
│   │   │   │   └── history.component.ts
│   │   │   ├── invoices
│   │   │   │   ├── invoices.component.html
│   │   │   │   ├── invoices.component.scss
│   │   │   │   ├── invoices.component.spec.ts
│   │   │   │   └── invoices.component.ts
│   │   │   ├── payment
│   │   │   │   ├── payment.component.html
│   │   │   │   ├── payment.component.scss
│   │   │   │   ├── payment.component.spec.ts
│   │   │   │   └── payment.component.ts
│   │   │   ├── payment-skeleton
│   │   │   │   ├── payment-skeleton.component.html
│   │   │   │   ├── payment-skeleton.component.scss
│   │   │   │   ├── payment-skeleton.component.spec.ts
│   │   │   │   └── payment-skeleton.component.ts
│   │   │   ├── premium-plan-skeleton
│   │   │   │   ├── premium-plan-skeleton.component.html
│   │   │   │   ├── premium-plan-skeleton.component.scss
│   │   │   │   ├── premium-plan-skeleton.component.spec.ts
│   │   │   │   └── premium-plan-skeleton.component.ts
│   │   │   ├── pricing-modal
│   │   │   │   ├── pricing-modal.component.html
│   │   │   │   ├── pricing-modal.component.scss
│   │   │   │   ├── pricing-modal.component.spec.ts
│   │   │   │   └── pricing-modal.component.ts
│   │   │   ├── product-detail
│   │   │   │   ├── product-detail.component.html
│   │   │   │   ├── product-detail.component.scss
│   │   │   │   ├── product-detail.component.spec.ts
│   │   │   │   └── product-detail.component.ts
│   │   │   └── users
│   │   │       ├── users.component.html
│   │   │       ├── users.component.scss
│   │   │       ├── users.component.spec.ts
│   │   │       └── users.component.ts
│   │   ├── models
│   │   │   ├── channel.model.ts
│   │   │   ├── customer.model.ts
│   │   │   ├── index.ts
│   │   │   ├── instance.model.ts
│   │   │   ├── invoice.model.ts
│   │   │   ├── product.model.ts
│   │   │   └── subscription.model.ts
│   │   ├── pipes
│   │   │   └── product.pipe.ts
│   │   └── service
│   │       ├── admin.service.spec.ts
│   │       ├── admin.service.ts
│   │       ├── channel.service.ts
│   │       ├── chargebee.service.ts
│   │       ├── compute.service.ts
│   │       ├── index.ts
│   │       └── ringcentral.service.ts
│   ├── app-config.ts
│   ├── app-routing.module.ts
│   ├── app.component.html
│   ├── app.component.scss
│   ├── app.component.ts
│   ├── app.globalConstants.ts
│   ├── app.module.ts
│   ├── auth
│   │   ├── helpers
│   │   │   ├── error.interceptor.ts
│   │   │   ├── fake-backend.ts
│   │   │   ├── index.ts
│   │   │   └── jwt.interceptor.ts
│   │   ├── models
│   │   │   ├── index.ts
│   │   │   ├── role.ts
│   │   │   └── user.ts
│   │   └── service
│   │       ├── authentication.service.ts
│   │       ├── index.ts
│   │       └── user.service.ts
│   ├── base
│   │   ├── account-signup
│   │   │   ├── account-signup-routing.module.ts
│   │   │   ├── account-signup.module.ts
│   │   │   ├── account-signup.service.spec.ts
│   │   │   ├── account-signup.service.ts
│   │   │   └── components
│   │   │       └── account-signup
│   │   │           ├── account-signup.component.html
│   │   │           ├── account-signup.component.scss
│   │   │           ├── account-signup.component.spec.ts
│   │   │           └── account-signup.component.ts
│   │   ├── agent
│   │   │   ├── agent-routing.module.ts
│   │   │   ├── agent.module.ts
│   │   │   ├── components
│   │   │   │   ├── agent-api-token
│   │   │   │   │   ├── agent-api-token.component.html
│   │   │   │   │   ├── agent-api-token.component.scss
│   │   │   │   │   ├── agent-api-token.component.spec.ts
│   │   │   │   │   └── agent-api-token.component.ts
│   │   │   │   ├── agent-cpu
│   │   │   │   │   ├── agent-cpu.component.html
│   │   │   │   │   ├── agent-cpu.component.scss
│   │   │   │   │   ├── agent-cpu.component.spec.ts
│   │   │   │   │   └── agent-cpu.component.ts
│   │   │   │   ├── agent-design
│   │   │   │   │   ├── agent-design.component.html
│   │   │   │   │   ├── agent-design.component.scss
│   │   │   │   │   ├── agent-design.component.spec.ts
│   │   │   │   │   └── agent-design.component.ts
│   │   │   │   ├── agent-detail
│   │   │   │   │   ├── agent-detail.component.html
│   │   │   │   │   ├── agent-detail.component.scss
│   │   │   │   │   ├── agent-detail.component.spec.ts
│   │   │   │   │   └── agent-detail.component.ts
│   │   │   │   ├── agent-edit
│   │   │   │   │   ├── agent-edit.component.html
│   │   │   │   │   ├── agent-edit.component.scss
│   │   │   │   │   ├── agent-edit.component.spec.ts
│   │   │   │   │   └── agent-edit.component.ts
│   │   │   │   ├── agent-grid
│   │   │   │   │   ├── agent-grid.component.html
│   │   │   │   │   ├── agent-grid.component.scss
│   │   │   │   │   ├── agent-grid.component.spec.ts
│   │   │   │   │   └── agent-grid.component.ts
│   │   │   │   ├── agent-load
│   │   │   │   │   ├── agent-load.component.html
│   │   │   │   │   ├── agent-load.component.scss
│   │   │   │   │   ├── agent-load.component.spec.ts
│   │   │   │   │   └── agent-load.component.ts
│   │   │   │   ├── agent-name-design
│   │   │   │   │   ├── agent-name-design.component.html
│   │   │   │   │   ├── agent-name-design.component.scss
│   │   │   │   │   ├── agent-name-design.component.spec.ts
│   │   │   │   │   └── agent-name-design.component.ts
│   │   │   │   ├── agent-progress
│   │   │   │   │   ├── agent-progress.component.html
│   │   │   │   │   ├── agent-progress.component.scss
│   │   │   │   │   ├── agent-progress.component.spec.ts
│   │   │   │   │   └── agent-progress.component.ts
│   │   │   │   └── agent-version
│   │   │   │       ├── agent-version.component.html
│   │   │   │       ├── agent-version.component.scss
│   │   │   │       ├── agent-version.component.spec.ts
│   │   │   │       └── agent-version.component.ts
│   │   │   └── services
│   │   │       ├── agent.service.spec.ts
│   │   │       └── agent.service.ts
│   │   ├── agent-installation
│   │   │   ├── agent-installation-routing.module.ts
│   │   │   ├── agent-installation.module.ts
│   │   │   └── components
│   │   │       ├── agent-download
│   │   │       │   ├── agent-download.component.html
│   │   │       │   ├── agent-download.component.scss
│   │   │       │   ├── agent-download.component.spec.ts
│   │   │       │   └── agent-download.component.ts
│   │   │       ├── agent-installation-image-viewer
│   │   │       │   ├── agent-installation-image-viewer.component.html
│   │   │       │   ├── agent-installation-image-viewer.component.scss
│   │   │       │   ├── agent-installation-image-viewer.component.spec.ts
│   │   │       │   └── agent-installation-image-viewer.component.ts
│   │   │       └── agent-installation-view
│   │   │           ├── agent-installation-view.component.html
│   │   │           ├── agent-installation-view.component.scss
│   │   │           ├── agent-installation-view.component.spec.ts
│   │   │           └── agent-installation-view.component.ts
│   │   ├── agent-token
│   │   │   ├── agent-token-routing.module.ts
│   │   │   ├── agent-token.module.ts
│   │   │   └── components
│   │   │       └── agent-token
│   │   │           ├── agent-token.component.html
│   │   │           ├── agent-token.component.scss
│   │   │           ├── agent-token.component.spec.ts
│   │   │           └── agent-token.component.ts
│   │   ├── api-registration
│   │   │   ├── api-registration-routing.module.ts
│   │   │   ├── api-registration.module.ts
│   │   │   ├── components
│   │   │   │   ├── api-registration
│   │   │   │   │   ├── api-registration.component.html
│   │   │   │   │   ├── api-registration.component.scss
│   │   │   │   │   ├── api-registration.component.spec.ts
│   │   │   │   │   └── api-registration.component.ts
│   │   │   │   └── api-registration-grid
│   │   │   │       ├── api-registration-grid.component.html
│   │   │   │       ├── api-registration-grid.component.scss
│   │   │   │       ├── api-registration-grid.component.spec.ts
│   │   │   │       └── api-registration-grid.component.ts
│   │   │   └── services
│   │   │       ├── api-registration.service.spec.ts
│   │   │       └── api-registration.service.ts
│   │   ├── asset
│   │   │   ├── asset-routing.module.ts
│   │   │   ├── asset.module.ts
│   │   │   ├── components
│   │   │   │   ├── add-attachment
│   │   │   │   │   ├── add-attachment.component.html
│   │   │   │   │   ├── add-attachment.component.scss
│   │   │   │   │   ├── add-attachment.component.spec.ts
│   │   │   │   │   └── add-attachment.component.ts
│   │   │   │   ├── add-audit-details
│   │   │   │   │   ├── add-audit-details.component.html
│   │   │   │   │   ├── add-audit-details.component.scss
│   │   │   │   │   ├── add-audit-details.component.spec.ts
│   │   │   │   │   └── add-audit-details.component.ts
│   │   │   │   ├── add-field
│   │   │   │   │   ├── add-field.component.html
│   │   │   │   │   ├── add-field.component.scss
│   │   │   │   │   ├── add-field.component.spec.ts
│   │   │   │   │   └── add-field.component.ts
│   │   │   │   ├── add-relation
│   │   │   │   │   ├── add-relation.component.html
│   │   │   │   │   ├── add-relation.component.scss
│   │   │   │   │   ├── add-relation.component.spec.ts
│   │   │   │   │   └── add-relation.component.ts
│   │   │   │   ├── advanced-resource-configuration
│   │   │   │   │   ├── advanced-resource-configuration.component.html
│   │   │   │   │   ├── advanced-resource-configuration.component.scss
│   │   │   │   │   ├── advanced-resource-configuration.component.spec.ts
│   │   │   │   │   └── advanced-resource-configuration.component.ts
│   │   │   │   ├── advanced-resource-configuration-actions
│   │   │   │   │   ├── advanced-resource-configuration-actions.component.html
│   │   │   │   │   ├── advanced-resource-configuration-actions.component.scss
│   │   │   │   │   ├── advanced-resource-configuration-actions.component.spec.ts
│   │   │   │   │   └── advanced-resource-configuration-actions.component.ts
│   │   │   │   ├── advanced-resource-configuration-add
│   │   │   │   │   ├── advanced-resource-configuration-add.component.html
│   │   │   │   │   ├── advanced-resource-configuration-add.component.scss
│   │   │   │   │   ├── advanced-resource-configuration-add.component.spec.ts
│   │   │   │   │   └── advanced-resource-configuration-add.component.ts
│   │   │   │   ├── arc-aiops-config
│   │   │   │   │   ├── arc-aiops-config.component.html
│   │   │   │   │   ├── arc-aiops-config.component.scss
│   │   │   │   │   ├── arc-aiops-config.component.spec.ts
│   │   │   │   │   └── arc-aiops-config.component.ts
│   │   │   │   ├── asset-activity
│   │   │   │   │   ├── asset-activity.component.html
│   │   │   │   │   ├── asset-activity.component.scss
│   │   │   │   │   ├── asset-activity.component.spec.ts
│   │   │   │   │   └── asset-activity.component.ts
│   │   │   │   ├── asset-audit
│   │   │   │   │   ├── asset-audit.component.html
│   │   │   │   │   ├── asset-audit.component.scss
│   │   │   │   │   ├── asset-audit.component.spec.ts
│   │   │   │   │   └── asset-audit.component.ts
│   │   │   │   ├── asset-audit-count
│   │   │   │   │   ├── asset-audit-count.component.html
│   │   │   │   │   ├── asset-audit-count.component.scss
│   │   │   │   │   ├── asset-audit-count.component.spec.ts
│   │   │   │   │   └── asset-audit-count.component.ts
│   │   │   │   ├── asset-audit-record-grid
│   │   │   │   │   ├── asset-audit-record-grid.component.html
│   │   │   │   │   ├── asset-audit-record-grid.component.scss
│   │   │   │   │   ├── asset-audit-record-grid.component.spec.ts
│   │   │   │   │   └── asset-audit-record-grid.component.ts
│   │   │   │   ├── asset-audit-template
│   │   │   │   │   ├── asset-audit-template.component.html
│   │   │   │   │   ├── asset-audit-template.component.scss
│   │   │   │   │   ├── asset-audit-template.component.spec.ts
│   │   │   │   │   └── asset-audit-template.component.ts
│   │   │   │   ├── asset-bulk-update
│   │   │   │   │   ├── asset-bulk-update.component.html
│   │   │   │   │   ├── asset-bulk-update.component.scss
│   │   │   │   │   ├── asset-bulk-update.component.spec.ts
│   │   │   │   │   └── asset-bulk-update.component.ts
│   │   │   │   ├── asset-cli-connection
│   │   │   │   │   ├── asset-cli-connection.component.html
│   │   │   │   │   ├── asset-cli-connection.component.scss
│   │   │   │   │   ├── asset-cli-connection.component.spec.ts
│   │   │   │   │   └── asset-cli-connection.component.ts
│   │   │   │   ├── asset-csv-edit
│   │   │   │   │   ├── asset-csv-edit.component.html
│   │   │   │   │   ├── asset-csv-edit.component.scss
│   │   │   │   │   ├── asset-csv-edit.component.spec.ts
│   │   │   │   │   └── asset-csv-edit.component.ts
│   │   │   │   ├── asset-details
│   │   │   │   │   ├── asset-details.component.html
│   │   │   │   │   ├── asset-details.component.scss
│   │   │   │   │   ├── asset-details.component.spec.ts
│   │   │   │   │   └── asset-details.component.ts
│   │   │   │   ├── asset-device-details
│   │   │   │   │   ├── asset-device-details.component.html
│   │   │   │   │   ├── asset-device-details.component.scss
│   │   │   │   │   ├── asset-device-details.component.spec.ts
│   │   │   │   │   └── asset-device-details.component.ts
│   │   │   │   ├── asset-device-location
│   │   │   │   │   ├── asset-device-location.component.html
│   │   │   │   │   ├── asset-device-location.component.scss
│   │   │   │   │   ├── asset-device-location.component.spec.ts
│   │   │   │   │   └── asset-device-location.component.ts
│   │   │   │   ├── asset-device-olt-container
│   │   │   │   │   ├── asset-device-olt-container.component.html
│   │   │   │   │   ├── asset-device-olt-container.component.scss
│   │   │   │   │   ├── asset-device-olt-container.component.spec.ts
│   │   │   │   │   └── asset-device-olt-container.component.ts
│   │   │   │   ├── asset-device-ont-container
│   │   │   │   │   ├── asset-device-ont-container.component.html
│   │   │   │   │   ├── asset-device-ont-container.component.scss
│   │   │   │   │   ├── asset-device-ont-container.component.spec.ts
│   │   │   │   │   └── asset-device-ont-container.component.ts
│   │   │   │   ├── asset-device-owner
│   │   │   │   │   ├── asset-device-owner.component.html
│   │   │   │   │   ├── asset-device-owner.component.scss
│   │   │   │   │   ├── asset-device-owner.component.spec.ts
│   │   │   │   │   └── asset-device-owner.component.ts
│   │   │   │   ├── asset-device-router-container
│   │   │   │   │   ├── asset-device-router-container.component.html
│   │   │   │   │   ├── asset-device-router-container.component.scss
│   │   │   │   │   ├── asset-device-router-container.component.spec.ts
│   │   │   │   │   └── asset-device-router-container.component.ts
│   │   │   │   ├── asset-device-switch-container
│   │   │   │   │   ├── asset-device-switch-container.component.html
│   │   │   │   │   ├── asset-device-switch-container.component.scss
│   │   │   │   │   ├── asset-device-switch-container.component.spec.ts
│   │   │   │   │   └── asset-device-switch-container.component.ts
│   │   │   │   ├── asset-device-user
│   │   │   │   │   ├── asset-device-user.component.html
│   │   │   │   │   ├── asset-device-user.component.scss
│   │   │   │   │   ├── asset-device-user.component.spec.ts
│   │   │   │   │   └── asset-device-user.component.ts
│   │   │   │   ├── asset-diagnosis
│   │   │   │   │   ├── asset-diagnosis.component.html
│   │   │   │   │   ├── asset-diagnosis.component.scss
│   │   │   │   │   ├── asset-diagnosis.component.spec.ts
│   │   │   │   │   └── asset-diagnosis.component.ts
│   │   │   │   ├── asset-edit
│   │   │   │   │   ├── asset-edit.component.html
│   │   │   │   │   ├── asset-edit.component.scss
│   │   │   │   │   ├── asset-edit.component.spec.ts
│   │   │   │   │   └── asset-edit.component.ts
│   │   │   │   ├── asset-grid-name
│   │   │   │   │   ├── asset-grid-name.component.html
│   │   │   │   │   ├── asset-grid-name.component.scss
│   │   │   │   │   ├── asset-grid-name.component.spec.ts
│   │   │   │   │   └── asset-grid-name.component.ts
│   │   │   │   ├── asset-hardware
│   │   │   │   │   ├── asset-hardware.component.html
│   │   │   │   │   ├── asset-hardware.component.scss
│   │   │   │   │   ├── asset-hardware.component.spec.ts
│   │   │   │   │   └── asset-hardware.component.ts
│   │   │   │   ├── asset-interface
│   │   │   │   │   ├── asset-interface.component.html
│   │   │   │   │   ├── asset-interface.component.scss
│   │   │   │   │   ├── asset-interface.component.spec.ts
│   │   │   │   │   └── asset-interface.component.ts
│   │   │   │   ├── asset-license
│   │   │   │   │   ├── asset-license.component.html
│   │   │   │   │   ├── asset-license.component.scss
│   │   │   │   │   ├── asset-license.component.spec.ts
│   │   │   │   │   └── asset-license.component.ts
│   │   │   │   ├── asset-life-cycle
│   │   │   │   │   ├── asset-life-cycle.component.html
│   │   │   │   │   ├── asset-life-cycle.component.scss
│   │   │   │   │   ├── asset-life-cycle.component.spec.ts
│   │   │   │   │   └── asset-life-cycle.component.ts
│   │   │   │   ├── asset-log-grid-name
│   │   │   │   │   ├── asset-log-grid-name.component.html
│   │   │   │   │   ├── asset-log-grid-name.component.scss
│   │   │   │   │   ├── asset-log-grid-name.component.spec.ts
│   │   │   │   │   └── asset-log-grid-name.component.ts
│   │   │   │   ├── asset-log-info
│   │   │   │   │   ├── asset-log-info.component.html
│   │   │   │   │   ├── asset-log-info.component.scss
│   │   │   │   │   ├── asset-log-info.component.spec.ts
│   │   │   │   │   └── asset-log-info.component.ts
│   │   │   │   ├── asset-logs
│   │   │   │   │   ├── asset-logs.component.html
│   │   │   │   │   ├── asset-logs.component.scss
│   │   │   │   │   ├── asset-logs.component.spec.ts
│   │   │   │   │   └── asset-logs.component.ts
│   │   │   │   ├── asset-name
│   │   │   │   │   ├── asset-name.component.html
│   │   │   │   │   ├── asset-name.component.scss
│   │   │   │   │   ├── asset-name.component.spec.ts
│   │   │   │   │   └── asset-name.component.ts
│   │   │   │   ├── asset-rescan
│   │   │   │   │   ├── asset-rescan.component.html
│   │   │   │   │   ├── asset-rescan.component.scss
│   │   │   │   │   ├── asset-rescan.component.spec.ts
│   │   │   │   │   └── asset-rescan.component.ts
│   │   │   │   ├── asset-sekeleton
│   │   │   │   │   ├── asset-sekeleton.component.html
│   │   │   │   │   ├── asset-sekeleton.component.scss
│   │   │   │   │   ├── asset-sekeleton.component.spec.ts
│   │   │   │   │   └── asset-sekeleton.component.ts
│   │   │   │   ├── asset-software
│   │   │   │   │   ├── asset-software.component.html
│   │   │   │   │   ├── asset-software.component.scss
│   │   │   │   │   ├── asset-software.component.spec.ts
│   │   │   │   │   └── asset-software.component.ts
│   │   │   │   ├── asset-summary
│   │   │   │   │   ├── asset-summary.component.html
│   │   │   │   │   ├── asset-summary.component.scss
│   │   │   │   │   ├── asset-summary.component.spec.ts
│   │   │   │   │   └── asset-summary.component.ts
│   │   │   │   ├── asset-view
│   │   │   │   │   ├── asset-view.component.html
│   │   │   │   │   ├── asset-view.component.scss
│   │   │   │   │   ├── asset-view.component.spec.ts
│   │   │   │   │   └── asset-view.component.ts
│   │   │   │   ├── asset-view-sidebar
│   │   │   │   │   ├── asset-view-sidebar.component.html
│   │   │   │   │   ├── asset-view-sidebar.component.scss
│   │   │   │   │   ├── asset-view-sidebar.component.spec.ts
│   │   │   │   │   └── asset-view-sidebar.component.ts
│   │   │   │   ├── audit-add-fields
│   │   │   │   │   ├── audit-add-fields.component.html
│   │   │   │   │   ├── audit-add-fields.component.scss
│   │   │   │   │   ├── audit-add-fields.component.spec.ts
│   │   │   │   │   └── audit-add-fields.component.ts
│   │   │   │   ├── bulk-resource-tag-untag
│   │   │   │   │   ├── bulk-resource-tag-untag.component.html
│   │   │   │   │   ├── bulk-resource-tag-untag.component.scss
│   │   │   │   │   ├── bulk-resource-tag-untag.component.spec.ts
│   │   │   │   │   └── bulk-resource-tag-untag.component.ts
│   │   │   │   ├── card-apexareachart
│   │   │   │   │   ├── card-apexareachart.component.html
│   │   │   │   │   ├── card-apexareachart.component.scss
│   │   │   │   │   ├── card-apexareachart.component.spec.ts
│   │   │   │   │   └── card-apexareachart.component.ts
│   │   │   │   ├── category-add
│   │   │   │   │   ├── category-add.component.html
│   │   │   │   │   ├── category-add.component.scss
│   │   │   │   │   ├── category-add.component.spec.ts
│   │   │   │   │   └── category-add.component.ts
│   │   │   │   ├── category-add-fields
│   │   │   │   │   ├── category-add-fields.component.html
│   │   │   │   │   ├── category-add-fields.component.scss
│   │   │   │   │   ├── category-add-fields.component.spec.ts
│   │   │   │   │   └── category-add-fields.component.ts
│   │   │   │   ├── category-property-role
│   │   │   │   │   ├── category-property-role.component.html
│   │   │   │   │   ├── category-property-role.component.scss
│   │   │   │   │   ├── category-property-role.component.spec.ts
│   │   │   │   │   └── category-property-role.component.ts
│   │   │   │   ├── category-template
│   │   │   │   │   ├── category-template.component.html
│   │   │   │   │   ├── category-template.component.scss
│   │   │   │   │   ├── category-template.component.spec.ts
│   │   │   │   │   └── category-template.component.ts
│   │   │   │   ├── cluster-datastores
│   │   │   │   │   ├── cluster-datastores.component.html
│   │   │   │   │   ├── cluster-datastores.component.scss
│   │   │   │   │   ├── cluster-datastores.component.spec.ts
│   │   │   │   │   └── cluster-datastores.component.ts
│   │   │   │   ├── cluster-datastores-view
│   │   │   │   │   ├── cluster-datastores-view.component.html
│   │   │   │   │   ├── cluster-datastores-view.component.scss
│   │   │   │   │   ├── cluster-datastores-view.component.spec.ts
│   │   │   │   │   └── cluster-datastores-view.component.ts
│   │   │   │   ├── cluster-datatable
│   │   │   │   │   ├── cluster-datatable.component.html
│   │   │   │   │   ├── cluster-datatable.component.scss
│   │   │   │   │   ├── cluster-datatable.component.spec.ts
│   │   │   │   │   └── cluster-datatable.component.ts
│   │   │   │   ├── cluster-host
│   │   │   │   │   ├── cluster-host.component.html
│   │   │   │   │   ├── cluster-host.component.scss
│   │   │   │   │   ├── cluster-host.component.spec.ts
│   │   │   │   │   └── cluster-host.component.ts
│   │   │   │   ├── cluster-host-card
│   │   │   │   │   ├── cluster-host-card.component.html
│   │   │   │   │   ├── cluster-host-card.component.scss
│   │   │   │   │   ├── cluster-host-card.component.spec.ts
│   │   │   │   │   └── cluster-host-card.component.ts
│   │   │   │   ├── cluster-host-view
│   │   │   │   │   ├── cluster-host-view.component.html
│   │   │   │   │   ├── cluster-host-view.component.scss
│   │   │   │   │   ├── cluster-host-view.component.spec.ts
│   │   │   │   │   └── cluster-host-view.component.ts
│   │   │   │   ├── cluster-summary
│   │   │   │   │   ├── cluster-summary-vm-card
│   │   │   │   │   │   ├── cluster-summary-vm-card.component.html
│   │   │   │   │   │   ├── cluster-summary-vm-card.component.scss
│   │   │   │   │   │   ├── cluster-summary-vm-card.component.spec.ts
│   │   │   │   │   │   └── cluster-summary-vm-card.component.ts
│   │   │   │   │   ├── cluster-summary.component.html
│   │   │   │   │   ├── cluster-summary.component.scss
│   │   │   │   │   ├── cluster-summary.component.spec.ts
│   │   │   │   │   └── cluster-summary.component.ts
│   │   │   │   ├── cluster-virtual-machine
│   │   │   │   │   ├── cluster-virtual-machine.component.html
│   │   │   │   │   ├── cluster-virtual-machine.component.scss
│   │   │   │   │   ├── cluster-virtual-machine.component.spec.ts
│   │   │   │   │   └── cluster-virtual-machine.component.ts
│   │   │   │   ├── cluster-vm-details-sidebar
│   │   │   │   │   ├── cluster-vm-details-sidebar.component.html
│   │   │   │   │   ├── cluster-vm-details-sidebar.component.scss
│   │   │   │   │   ├── cluster-vm-details-sidebar.component.spec.ts
│   │   │   │   │   └── cluster-vm-details-sidebar.component.ts
│   │   │   │   ├── cross-connection
│   │   │   │   │   ├── cross-connection.component.html
│   │   │   │   │   ├── cross-connection.component.scss
│   │   │   │   │   ├── cross-connection.component.spec.ts
│   │   │   │   │   └── cross-connection.component.ts
│   │   │   │   ├── edit-asset-fields-in-audit
│   │   │   │   │   ├── edit-asset-fields-in-audit.component.html
│   │   │   │   │   ├── edit-asset-fields-in-audit.component.scss
│   │   │   │   │   ├── edit-asset-fields-in-audit.component.spec.ts
│   │   │   │   │   └── edit-asset-fields-in-audit.component.ts
│   │   │   │   ├── export-asset-sidebar
│   │   │   │   │   ├── export-asset-sidebar.component.html
│   │   │   │   │   ├── export-asset-sidebar.component.scss
│   │   │   │   │   ├── export-asset-sidebar.component.spec.ts
│   │   │   │   │   └── export-asset-sidebar.component.ts
│   │   │   │   ├── field-grid
│   │   │   │   │   ├── field-grid.component.html
│   │   │   │   │   ├── field-grid.component.scss
│   │   │   │   │   ├── field-grid.component.spec.ts
│   │   │   │   │   └── field-grid.component.ts
│   │   │   │   ├── hardware-details
│   │   │   │   │   ├── hardware-details.component.html
│   │   │   │   │   ├── hardware-details.component.scss
│   │   │   │   │   ├── hardware-details.component.spec.ts
│   │   │   │   │   └── hardware-details.component.ts
│   │   │   │   ├── hardware-inventory
│   │   │   │   │   ├── hardware-inventory.component.html
│   │   │   │   │   ├── hardware-inventory.component.scss
│   │   │   │   │   ├── hardware-inventory.component.spec.ts
│   │   │   │   │   └── hardware-inventory.component.ts
│   │   │   │   ├── import-asset-sidebar
│   │   │   │   │   ├── import-asset-sidebar.component.html
│   │   │   │   │   ├── import-asset-sidebar.component.scss
│   │   │   │   │   ├── import-asset-sidebar.component.spec.ts
│   │   │   │   │   └── import-asset-sidebar.component.ts
│   │   │   │   ├── interface
│   │   │   │   │   ├── interface.component.html
│   │   │   │   │   ├── interface.component.scss
│   │   │   │   │   ├── interface.component.spec.ts
│   │   │   │   │   └── interface.component.ts
│   │   │   │   ├── interface-activate-sidebar
│   │   │   │   │   ├── interface-activate-sidebar.component.html
│   │   │   │   │   ├── interface-activate-sidebar.component.scss
│   │   │   │   │   ├── interface-activate-sidebar.component.spec.ts
│   │   │   │   │   └── interface-activate-sidebar.component.ts
│   │   │   │   ├── interface-ptp-sidebar
│   │   │   │   │   ├── interface-ptp-sidebar.component.html
│   │   │   │   │   ├── interface-ptp-sidebar.component.scss
│   │   │   │   │   ├── interface-ptp-sidebar.component.spec.ts
│   │   │   │   │   └── interface-ptp-sidebar.component.ts
│   │   │   │   ├── inventory-list
│   │   │   │   │   ├── inventory-list.component.html
│   │   │   │   │   ├── inventory-list.component.scss
│   │   │   │   │   ├── inventory-list.component.spec.ts
│   │   │   │   │   └── inventory-list.component.ts
│   │   │   │   ├── inventory-service-detail-sidebar
│   │   │   │   │   ├── inventory-service-detail-sidebar.component.html
│   │   │   │   │   ├── inventory-service-detail-sidebar.component.scss
│   │   │   │   │   ├── inventory-service-detail-sidebar.component.spec.ts
│   │   │   │   │   └── inventory-service-detail-sidebar.component.ts
│   │   │   │   ├── inventory-tree
│   │   │   │   │   ├── inventory-tree.component.html
│   │   │   │   │   ├── inventory-tree.component.scss
│   │   │   │   │   ├── inventory-tree.component.spec.ts
│   │   │   │   │   └── inventory-tree.component.ts
│   │   │   │   ├── inventory-tree-ont
│   │   │   │   │   ├── inventory-tree-ont.component.html
│   │   │   │   │   ├── inventory-tree-ont.component.scss
│   │   │   │   │   ├── inventory-tree-ont.component.spec.ts
│   │   │   │   │   └── inventory-tree-ont.component.ts
│   │   │   │   ├── inventory-tree-sidebar
│   │   │   │   │   ├── inventory-tree-sidebar.component.html
│   │   │   │   │   ├── inventory-tree-sidebar.component.scss
│   │   │   │   │   ├── inventory-tree-sidebar.component.spec.ts
│   │   │   │   │   └── inventory-tree-sidebar.component.ts
│   │   │   │   ├── itasset
│   │   │   │   │   ├── itasset.component.html
│   │   │   │   │   ├── itasset.component.scss
│   │   │   │   │   ├── itasset.component.spec.ts
│   │   │   │   │   └── itasset.component.ts
│   │   │   │   ├── itasset-list
│   │   │   │   │   ├── filter.pipe.ts
│   │   │   │   │   ├── focus.directive.spec.ts
│   │   │   │   │   ├── focus.directive.ts
│   │   │   │   │   ├── itasset-list.component.html
│   │   │   │   │   ├── itasset-list.component.scss
│   │   │   │   │   ├── itasset-list.component.spec.ts
│   │   │   │   │   └── itasset-list.component.ts
│   │   │   │   ├── itasset-sidebar
│   │   │   │   │   ├── itasset-sidebar.component.html
│   │   │   │   │   ├── itasset-sidebar.component.scss
│   │   │   │   │   ├── itasset-sidebar.component.spec.ts
│   │   │   │   │   └── itasset-sidebar.component.ts
│   │   │   │   ├── item
│   │   │   │   │   ├── item.component.html
│   │   │   │   │   ├── item.component.scss
│   │   │   │   │   ├── item.component.spec.ts
│   │   │   │   │   └── item.component.ts
│   │   │   │   ├── item-classification-config
│   │   │   │   │   ├── item-classification-config.component.html
│   │   │   │   │   ├── item-classification-config.component.scss
│   │   │   │   │   ├── item-classification-config.component.spec.ts
│   │   │   │   │   └── item-classification-config.component.ts
│   │   │   │   ├── item-classification-config-sidebar
│   │   │   │   │   ├── item-classification-config-sidebar.component.html
│   │   │   │   │   ├── item-classification-config-sidebar.component.scss
│   │   │   │   │   ├── item-classification-config-sidebar.component.spec.ts
│   │   │   │   │   └── item-classification-config-sidebar.component.ts
│   │   │   │   ├── item-classification-filter-config
│   │   │   │   │   ├── item-classification-filter-config.component.html
│   │   │   │   │   ├── item-classification-filter-config.component.scss
│   │   │   │   │   ├── item-classification-filter-config.component.spec.ts
│   │   │   │   │   └── item-classification-filter-config.component.ts
│   │   │   │   ├── item-classification-grid
│   │   │   │   │   ├── item-classification-grid.component.html
│   │   │   │   │   ├── item-classification-grid.component.scss
│   │   │   │   │   ├── item-classification-grid.component.spec.ts
│   │   │   │   │   └── item-classification-grid.component.ts
│   │   │   │   ├── item-type
│   │   │   │   │   ├── item-type.component.html
│   │   │   │   │   ├── item-type.component.scss
│   │   │   │   │   ├── item-type.component.spec.ts
│   │   │   │   │   └── item-type.component.ts
│   │   │   │   ├── itsm-view
│   │   │   │   │   ├── itsm-view.component.html
│   │   │   │   │   ├── itsm-view.component.scss
│   │   │   │   │   ├── itsm-view.component.spec.ts
│   │   │   │   │   └── itsm-view.component.ts
│   │   │   │   ├── location
│   │   │   │   │   ├── location.component.html
│   │   │   │   │   ├── location.component.scss
│   │   │   │   │   ├── location.component.spec.ts
│   │   │   │   │   └── location.component.ts
│   │   │   │   ├── modify-uni-port-sidebar
│   │   │   │   │   ├── modify-uni-port-sidebar.component.html
│   │   │   │   │   ├── modify-uni-port-sidebar.component.scss
│   │   │   │   │   ├── modify-uni-port-sidebar.component.spec.ts
│   │   │   │   │   └── modify-uni-port-sidebar.component.ts
│   │   │   │   ├── olt-backup-sidebar
│   │   │   │   │   ├── olt-backup-sidebar.component.html
│   │   │   │   │   ├── olt-backup-sidebar.component.scss
│   │   │   │   │   ├── olt-backup-sidebar.component.spec.ts
│   │   │   │   │   └── olt-backup-sidebar.component.ts
│   │   │   │   ├── olt-card-switchover-sidebar
│   │   │   │   │   ├── olt-card-switchover-sidebar.component.html
│   │   │   │   │   ├── olt-card-switchover-sidebar.component.scss
│   │   │   │   │   ├── olt-card-switchover-sidebar.component.spec.ts
│   │   │   │   │   └── olt-card-switchover-sidebar.component.ts
│   │   │   │   ├── olt-fan-status-sidebar
│   │   │   │   │   ├── olt-fan-status-sidebar.component.html
│   │   │   │   │   ├── olt-fan-status-sidebar.component.scss
│   │   │   │   │   ├── olt-fan-status-sidebar.component.spec.ts
│   │   │   │   │   └── olt-fan-status-sidebar.component.ts
│   │   │   │   ├── olt-restore-sidebar
│   │   │   │   │   ├── olt-restore-sidebar.component.html
│   │   │   │   │   ├── olt-restore-sidebar.component.scss
│   │   │   │   │   ├── olt-restore-sidebar.component.spec.ts
│   │   │   │   │   └── olt-restore-sidebar.component.ts
│   │   │   │   ├── olt-resync-sidebar
│   │   │   │   │   ├── olt-resync-sidebar.component.html
│   │   │   │   │   ├── olt-resync-sidebar.component.scss
│   │   │   │   │   ├── olt-resync-sidebar.component.spec.ts
│   │   │   │   │   └── olt-resync-sidebar.component.ts
│   │   │   │   ├── olt-upgrade-sidebar
│   │   │   │   │   ├── olt-upgrade-sidebar.component.html
│   │   │   │   │   ├── olt-upgrade-sidebar.component.scss
│   │   │   │   │   ├── olt-upgrade-sidebar.component.spec.ts
│   │   │   │   │   └── olt-upgrade-sidebar.component.ts
│   │   │   │   ├── ont-aes-sidebar
│   │   │   │   │   ├── ont-aes-sidebar.component.html
│   │   │   │   │   ├── ont-aes-sidebar.component.scss
│   │   │   │   │   ├── ont-aes-sidebar.component.spec.ts
│   │   │   │   │   └── ont-aes-sidebar.component.ts
│   │   │   │   ├── ont-ccu-sidebar
│   │   │   │   │   ├── ont-ccu-sidebar.component.html
│   │   │   │   │   ├── ont-ccu-sidebar.component.scss
│   │   │   │   │   ├── ont-ccu-sidebar.component.spec.ts
│   │   │   │   │   └── ont-ccu-sidebar.component.ts
│   │   │   │   ├── ont-grid-view
│   │   │   │   │   ├── ont-grid-view.component.html
│   │   │   │   │   ├── ont-grid-view.component.scss
│   │   │   │   │   ├── ont-grid-view.component.spec.ts
│   │   │   │   │   └── ont-grid-view.component.ts
│   │   │   │   ├── ont-optical-sidebar
│   │   │   │   │   ├── ont-optical-sidebar.component.html
│   │   │   │   │   ├── ont-optical-sidebar.component.scss
│   │   │   │   │   ├── ont-optical-sidebar.component.spec.ts
│   │   │   │   │   └── ont-optical-sidebar.component.ts
│   │   │   │   ├── ont-replace-sidebar
│   │   │   │   │   ├── ont-replace-sidebar.component.html
│   │   │   │   │   ├── ont-replace-sidebar.component.scss
│   │   │   │   │   ├── ont-replace-sidebar.component.spec.ts
│   │   │   │   │   └── ont-replace-sidebar.component.ts
│   │   │   │   ├── ont-serial-modification-sidebar
│   │   │   │   │   ├── ont-serial-modification-sidebar.component.html
│   │   │   │   │   ├── ont-serial-modification-sidebar.component.scss
│   │   │   │   │   ├── ont-serial-modification-sidebar.component.spec.ts
│   │   │   │   │   └── ont-serial-modification-sidebar.component.ts
│   │   │   │   ├── ont-thresholds-sidebar
│   │   │   │   │   ├── ont-thresholds-sidebar.component.html
│   │   │   │   │   ├── ont-thresholds-sidebar.component.scss
│   │   │   │   │   ├── ont-thresholds-sidebar.component.spec.ts
│   │   │   │   │   └── ont-thresholds-sidebar.component.ts
│   │   │   │   ├── ont-upgrade-sidebar
│   │   │   │   │   ├── ont-upgrade-sidebar.component.html
│   │   │   │   │   ├── ont-upgrade-sidebar.component.scss
│   │   │   │   │   ├── ont-upgrade-sidebar.component.spec.ts
│   │   │   │   │   └── ont-upgrade-sidebar.component.ts
│   │   │   │   ├── panel-view
│   │   │   │   │   ├── panel-view.component.html
│   │   │   │   │   ├── panel-view.component.scss
│   │   │   │   │   ├── panel-view.component.spec.ts
│   │   │   │   │   └── panel-view.component.ts
│   │   │   │   ├── poll-profile
│   │   │   │   │   ├── poll-profile.component.html
│   │   │   │   │   ├── poll-profile.component.scss
│   │   │   │   │   ├── poll-profile.component.spec.ts
│   │   │   │   │   └── poll-profile.component.ts
│   │   │   │   ├── port-utilization
│   │   │   │   │   ├── port-utilization.component.html
│   │   │   │   │   ├── port-utilization.component.scss
│   │   │   │   │   ├── port-utilization.component.spec.ts
│   │   │   │   │   └── port-utilization.component.ts
│   │   │   │   ├── print-asset-sidebar
│   │   │   │   │   ├── print-asset-sidebar.component.html
│   │   │   │   │   ├── print-asset-sidebar.component.scss
│   │   │   │   │   ├── print-asset-sidebar.component.spec.ts
│   │   │   │   │   └── print-asset-sidebar.component.ts
│   │   │   │   ├── relation
│   │   │   │   │   ├── relation.component.html
│   │   │   │   │   ├── relation.component.scss
│   │   │   │   │   ├── relation.component.spec.ts
│   │   │   │   │   └── relation.component.ts
│   │   │   │   ├── resource-detail
│   │   │   │   │   ├── resource-detail.component.html
│   │   │   │   │   ├── resource-detail.component.scss
│   │   │   │   │   ├── resource-detail.component.spec.ts
│   │   │   │   │   └── resource-detail.component.ts
│   │   │   │   ├── resource-edit
│   │   │   │   │   ├── resource-edit.component.html
│   │   │   │   │   ├── resource-edit.component.scss
│   │   │   │   │   ├── resource-edit.component.spec.ts
│   │   │   │   │   └── resource-edit.component.ts
│   │   │   │   ├── resource-report-sidebar
│   │   │   │   │   ├── resource-report-sidebar.component.html
│   │   │   │   │   ├── resource-report-sidebar.component.scss
│   │   │   │   │   ├── resource-report-sidebar.component.spec.ts
│   │   │   │   │   └── resource-report-sidebar.component.ts
│   │   │   │   ├── resource-statistic
│   │   │   │   │   ├── resource-statistic.component.html
│   │   │   │   │   ├── resource-statistic.component.spec.ts
│   │   │   │   │   └── resource-statistic.component.ts
│   │   │   │   ├── resource-statistics
│   │   │   │   │   ├── resource-statistics.component.html
│   │   │   │   │   ├── resource-statistics.component.scss
│   │   │   │   │   ├── resource-statistics.component.spec.ts
│   │   │   │   │   └── resource-statistics.component.ts
│   │   │   │   ├── resources
│   │   │   │   │   ├── resources.component.html
│   │   │   │   │   ├── resources.component.scss
│   │   │   │   │   ├── resources.component.spec.ts
│   │   │   │   │   └── resources.component.ts
│   │   │   │   ├── select-data
│   │   │   │   │   ├── select-data.component.html
│   │   │   │   │   ├── select-data.component.scss
│   │   │   │   │   ├── select-data.component.spec.ts
│   │   │   │   │   └── select-data.component.ts
│   │   │   │   ├── services-tab-page
│   │   │   │   │   ├── services-tab-page.component.html
│   │   │   │   │   ├── services-tab-page.component.scss
│   │   │   │   │   ├── services-tab-page.component.spec.ts
│   │   │   │   │   └── services-tab-page.component.ts
│   │   │   │   ├── set-tag
│   │   │   │   │   ├── set-tag.component.html
│   │   │   │   │   ├── set-tag.component.scss
│   │   │   │   │   ├── set-tag.component.spec.ts
│   │   │   │   │   └── set-tag.component.ts
│   │   │   │   ├── software-name-design
│   │   │   │   │   ├── software-name-design.component.html
│   │   │   │   │   ├── software-name-design.component.scss
│   │   │   │   │   ├── software-name-design.component.spec.ts
│   │   │   │   │   └── software-name-design.component.ts
│   │   │   │   ├── tickets
│   │   │   │   │   ├── tickets.component.html
│   │   │   │   │   ├── tickets.component.scss
│   │   │   │   │   ├── tickets.component.spec.ts
│   │   │   │   │   └── tickets.component.ts
│   │   │   │   ├── topology-links
│   │   │   │   │   ├── topology-links.component.html
│   │   │   │   │   ├── topology-links.component.scss
│   │   │   │   │   ├── topology-links.component.spec.ts
│   │   │   │   │   └── topology-links.component.ts
│   │   │   │   ├── update-badwidth-sidebar
│   │   │   │   │   ├── update-badwidth-sidebar.component.html
│   │   │   │   │   ├── update-badwidth-sidebar.component.scss
│   │   │   │   │   ├── update-badwidth-sidebar.component.spec.ts
│   │   │   │   │   └── update-badwidth-sidebar.component.ts
│   │   │   │   ├── view-onts-sidebar
│   │   │   │   │   ├── view-onts-sidebar.component.html
│   │   │   │   │   ├── view-onts-sidebar.component.scss
│   │   │   │   │   ├── view-onts-sidebar.component.spec.ts
│   │   │   │   │   └── view-onts-sidebar.component.ts
│   │   │   │   ├── view-services-sidebar
│   │   │   │   │   ├── view-services-sidebar.component.html
│   │   │   │   │   ├── view-services-sidebar.component.scss
│   │   │   │   │   ├── view-services-sidebar.component.spec.ts
│   │   │   │   │   └── view-services-sidebar.component.ts
│   │   │   │   ├── wlc-access-point
│   │   │   │   │   ├── wlc-access-point.component.html
│   │   │   │   │   ├── wlc-access-point.component.scss
│   │   │   │   │   ├── wlc-access-point.component.spec.ts
│   │   │   │   │   └── wlc-access-point.component.ts
│   │   │   │   ├── wlc-access-point-info-sidebar
│   │   │   │   │   ├── wlc-access-point-info-sidebar.component.html
│   │   │   │   │   ├── wlc-access-point-info-sidebar.component.scss
│   │   │   │   │   ├── wlc-access-point-info-sidebar.component.spec.ts
│   │   │   │   │   └── wlc-access-point-info-sidebar.component.ts
│   │   │   │   └── wlc-summary
│   │   │   │       ├── wlc-summary.component.html
│   │   │   │       ├── wlc-summary.component.scss
│   │   │   │       ├── wlc-summary.component.spec.ts
│   │   │   │       └── wlc-summary.component.ts
│   │   │   ├── config
│   │   │   │   └── asset-image-src.json
│   │   │   └── services
│   │   │       ├── asset.service.spec.ts
│   │   │       ├── asset.service.ts
│   │   │       ├── marketplace-api.service.spec.ts
│   │   │       └── marketplace-api.service.ts
│   │   ├── asset-pso
│   │   │   ├── asset-pso-routing.module.ts
│   │   │   ├── asset-pso.module.ts
│   │   │   ├── components
│   │   │   │   ├── asset-pso
│   │   │   │   │   ├── asset-pso.component.html
│   │   │   │   │   ├── asset-pso.component.scss
│   │   │   │   │   ├── asset-pso.component.spec.ts
│   │   │   │   │   └── asset-pso.component.ts
│   │   │   │   ├── asset-pso-card
│   │   │   │   │   ├── asset-pso-card.component.html
│   │   │   │   │   ├── asset-pso-card.component.scss
│   │   │   │   │   ├── asset-pso-card.component.spec.ts
│   │   │   │   │   └── asset-pso-card.component.ts
│   │   │   │   ├── maintenance-schedule
│   │   │   │   │   ├── maintenance-schedule.component.html
│   │   │   │   │   ├── maintenance-schedule.component.scss
│   │   │   │   │   ├── maintenance-schedule.component.spec.ts
│   │   │   │   │   └── maintenance-schedule.component.ts
│   │   │   │   └── pso-schedule
│   │   │   │       ├── pso-schedule.component.html
│   │   │   │       ├── pso-schedule.component.scss
│   │   │   │       ├── pso-schedule.component.spec.ts
│   │   │   │       └── pso-schedule.component.ts
│   │   │   └── services
│   │   │       ├── asset-pso.service.spec.ts
│   │   │       └── asset-pso.service.ts
│   │   ├── asset-software
│   │   │   ├── asset-software-routing.module.ts
│   │   │   ├── asset-software.module.ts
│   │   │   ├── components
│   │   │   │   ├── allocate-license
│   │   │   │   │   ├── allocate-license.component.html
│   │   │   │   │   ├── allocate-license.component.scss
│   │   │   │   │   ├── allocate-license.component.spec.ts
│   │   │   │   │   └── allocate-license.component.ts
│   │   │   │   ├── inventory
│   │   │   │   │   ├── inventory.component.html
│   │   │   │   │   ├── inventory.component.scss
│   │   │   │   │   ├── inventory.component.spec.ts
│   │   │   │   │   └── inventory.component.ts
│   │   │   │   ├── inventory-list
│   │   │   │   │   ├── inventory-list.component.html
│   │   │   │   │   ├── inventory-list.component.scss
│   │   │   │   │   ├── inventory-list.component.spec.ts
│   │   │   │   │   └── inventory-list.component.ts
│   │   │   │   ├── inventory-sidebar
│   │   │   │   │   ├── inventory-sidebar.component.html
│   │   │   │   │   ├── inventory-sidebar.component.scss
│   │   │   │   │   ├── inventory-sidebar.component.spec.ts
│   │   │   │   │   └── inventory-sidebar.component.ts
│   │   │   │   ├── inventory-view
│   │   │   │   │   ├── inventory-view.component.html
│   │   │   │   │   ├── inventory-view.component.scss
│   │   │   │   │   ├── inventory-view.component.spec.ts
│   │   │   │   │   └── inventory-view.component.ts
│   │   │   │   ├── license
│   │   │   │   │   ├── license.component.html
│   │   │   │   │   ├── license.component.scss
│   │   │   │   │   ├── license.component.spec.ts
│   │   │   │   │   └── license.component.ts
│   │   │   │   ├── license-add
│   │   │   │   │   ├── license-add.component.html
│   │   │   │   │   ├── license-add.component.scss
│   │   │   │   │   ├── license-add.component.spec.ts
│   │   │   │   │   └── license-add.component.ts
│   │   │   │   ├── license-list
│   │   │   │   │   ├── license-list.component.html
│   │   │   │   │   ├── license-list.component.scss
│   │   │   │   │   ├── license-list.component.spec.ts
│   │   │   │   │   └── license-list.component.ts
│   │   │   │   ├── license-sidebar
│   │   │   │   │   ├── license-sidebar.component.html
│   │   │   │   │   ├── license-sidebar.component.scss
│   │   │   │   │   ├── license-sidebar.component.spec.ts
│   │   │   │   │   └── license-sidebar.component.ts
│   │   │   │   └── license-view
│   │   │   │       ├── license-view.component.html
│   │   │   │       ├── license-view.component.scss
│   │   │   │       ├── license-view.component.spec.ts
│   │   │   │       └── license-view.component.ts
│   │   │   └── services
│   │   │       ├── software-inventory.service.spec.ts
│   │   │       └── software-inventory.service.ts
│   │   ├── audit
│   │   │   ├── audit-routing.module.ts
│   │   │   ├── audit.module.ts
│   │   │   ├── components
│   │   │   │   └── audit-grid
│   │   │   │       ├── audit-grid.component.html
│   │   │   │       ├── audit-grid.component.scss
│   │   │   │       ├── audit-grid.component.spec.ts
│   │   │   │       └── audit-grid.component.ts
│   │   │   └── services
│   │   │       ├── audit.service.spec.ts
│   │   │       └── audit.service.ts
│   │   ├── auth
│   │   │   ├── auth-routing.module.ts
│   │   │   ├── auth.module.ts
│   │   │   ├── components
│   │   │   │   ├── forgot-password
│   │   │   │   │   ├── forgot-password.component.html
│   │   │   │   │   ├── forgot-password.component.scss
│   │   │   │   │   ├── forgot-password.component.spec.ts
│   │   │   │   │   └── forgot-password.component.ts
│   │   │   │   ├── login
│   │   │   │   │   ├── login.component.html
│   │   │   │   │   ├── login.component.scss
│   │   │   │   │   ├── login.component.spec.ts
│   │   │   │   │   └── login.component.ts
│   │   │   │   ├── new-forgot-password
│   │   │   │   │   ├── new-forgot-password.component.html
│   │   │   │   │   ├── new-forgot-password.component.scss
│   │   │   │   │   ├── new-forgot-password.component.spec.ts
│   │   │   │   │   └── new-forgot-password.component.ts
│   │   │   │   ├── new-login
│   │   │   │   │   ├── new-login.component.html
│   │   │   │   │   ├── new-login.component.scss
│   │   │   │   │   ├── new-login.component.spec.ts
│   │   │   │   │   └── new-login.component.ts
│   │   │   │   ├── new-otp-login
│   │   │   │   │   ├── new-otp-login.component.html
│   │   │   │   │   ├── new-otp-login.component.scss
│   │   │   │   │   ├── new-otp-login.component.spec.ts
│   │   │   │   │   └── new-otp-login.component.ts
│   │   │   │   ├── new-password-reset
│   │   │   │   │   ├── new-password-reset.component.html
│   │   │   │   │   ├── new-password-reset.component.scss
│   │   │   │   │   ├── new-password-reset.component.spec.ts
│   │   │   │   │   └── new-password-reset.component.ts
│   │   │   │   ├── new-register
│   │   │   │   │   ├── new-register.component.html
│   │   │   │   │   ├── new-register.component.scss
│   │   │   │   │   ├── new-register.component.spec.ts
│   │   │   │   │   └── new-register.component.ts
│   │   │   │   ├── new-slider
│   │   │   │   │   ├── new-slider.component.html
│   │   │   │   │   ├── new-slider.component.scss
│   │   │   │   │   ├── new-slider.component.spec.ts
│   │   │   │   │   └── new-slider.component.ts
│   │   │   │   ├── otp-login
│   │   │   │   │   ├── otp-login.component.html
│   │   │   │   │   ├── otp-login.component.scss
│   │   │   │   │   ├── otp-login.component.spec.ts
│   │   │   │   │   └── otp-login.component.ts
│   │   │   │   ├── password-expired
│   │   │   │   │   ├── password-expired.component.html
│   │   │   │   │   ├── password-expired.component.scss
│   │   │   │   │   ├── password-expired.component.spec.ts
│   │   │   │   │   └── password-expired.component.ts
│   │   │   │   ├── password-reset
│   │   │   │   │   ├── password-reset.component.html
│   │   │   │   │   ├── password-reset.component.scss
│   │   │   │   │   ├── password-reset.component.spec.ts
│   │   │   │   │   └── password-reset.component.ts
│   │   │   │   ├── redirect-handler
│   │   │   │   │   ├── redirect-handler.component.html
│   │   │   │   │   ├── redirect-handler.component.scss
│   │   │   │   │   ├── redirect-handler.component.spec.ts
│   │   │   │   │   └── redirect-handler.component.ts
│   │   │   │   ├── register
│   │   │   │   │   ├── register.component.html
│   │   │   │   │   ├── register.component.scss
│   │   │   │   │   ├── register.component.spec.ts
│   │   │   │   │   └── register.component.ts
│   │   │   │   └── selfservice-login
│   │   │   │       ├── selfservice-login.component.html
│   │   │   │       ├── selfservice-login.component.scss
│   │   │   │       ├── selfservice-login.component.spec.ts
│   │   │   │       └── selfservice-login.component.ts
│   │   │   └── services
│   │   │       ├── auth.posts.resolve.ts
│   │   │       ├── auth.service.spec.ts
│   │   │       └── auth.service.ts
│   │   ├── authsso
│   │   │   ├── authlogin
│   │   │   │   ├── authlogin.component.html
│   │   │   │   ├── authlogin.component.scss
│   │   │   │   ├── authlogin.component.spec.ts
│   │   │   │   └── authlogin.component.ts
│   │   │   ├── authsso-routing.module.ts
│   │   │   ├── authsso.module.ts
│   │   │   ├── component
│   │   │   │   └── authsso
│   │   │   │       ├── authsso.component.html
│   │   │   │       ├── authsso.component.scss
│   │   │   │       ├── authsso.component.spec.ts
│   │   │   │       └── authsso.component.ts
│   │   │   └── services
│   │   │       ├── authsso.service.spec.ts
│   │   │       └── authsso.service.ts
│   │   ├── blacklist-whitelist
│   │   │   ├── blacklist-whitelist-routing.module.ts
│   │   │   ├── blacklist-whitelist.module.ts
│   │   │   ├── components
│   │   │   │   ├── blacklist-whitelist
│   │   │   │   │   ├── blacklist-whitelist.component.html
│   │   │   │   │   ├── blacklist-whitelist.component.scss
│   │   │   │   │   ├── blacklist-whitelist.component.spec.ts
│   │   │   │   │   └── blacklist-whitelist.component.ts
│   │   │   │   └── blacklist-whitelist-grid
│   │   │   │       ├── blacklist-whitelist-grid.component.html
│   │   │   │       ├── blacklist-whitelist-grid.component.scss
│   │   │   │       ├── blacklist-whitelist-grid.component.spec.ts
│   │   │   │       └── blacklist-whitelist-grid.component.ts
│   │   │   └── services
│   │   │       ├── blacklist-whitelist.service.spec.ts
│   │   │       └── blacklist-whitelist.service.ts
│   │   ├── brand-styling
│   │   │   ├── brand-styling-routing.module.ts
│   │   │   ├── brand-styling.module.ts
│   │   │   ├── brand-styling.service.spec.ts
│   │   │   ├── brand-styling.service.ts
│   │   │   └── components
│   │   │       ├── brand-styling
│   │   │       │   ├── brand-styling.component.html
│   │   │       │   ├── brand-styling.component.scss
│   │   │       │   ├── brand-styling.component.spec.ts
│   │   │       │   └── brand-styling.component.ts
│   │   │       ├── email-preview
│   │   │       │   ├── email-preview.component.html
│   │   │       │   ├── email-preview.component.scss
│   │   │       │   ├── email-preview.component.spec.ts
│   │   │       │   └── email-preview.component.ts
│   │   │       └── report
│   │   │           ├── report.component.html
│   │   │           ├── report.component.scss
│   │   │           ├── report.component.spec.ts
│   │   │           └── report.component.ts
│   │   ├── business-hour
│   │   │   ├── business-hour-routing.module.ts
│   │   │   ├── business-hour.module.ts
│   │   │   ├── components
│   │   │   │   ├── business-card
│   │   │   │   │   ├── business-card.component.html
│   │   │   │   │   ├── business-card.component.scss
│   │   │   │   │   ├── business-card.component.spec.ts
│   │   │   │   │   └── business-card.component.ts
│   │   │   │   ├── business-grid
│   │   │   │   │   ├── business-grid.component.html
│   │   │   │   │   ├── business-grid.component.scss
│   │   │   │   │   ├── business-grid.component.spec.ts
│   │   │   │   │   └── business-grid.component.ts
│   │   │   │   └── business-profile
│   │   │   │       ├── business-profile.animation.ts
│   │   │   │       ├── business-profile.component.html
│   │   │   │       ├── business-profile.component.scss
│   │   │   │       └── business-profile.component.ts
│   │   │   └── services
│   │   │       ├── business-hour.service.spec.ts
│   │   │       └── business-hour.service.ts
│   │   ├── businesscatalogue
│   │   │   ├── businesscatalogue-routing.module.ts
│   │   │   ├── businesscatalogue.module.ts
│   │   │   ├── components
│   │   │   │   ├── business-catalogue
│   │   │   │   │   ├── business-catalogue.component.html
│   │   │   │   │   ├── business-catalogue.component.scss
│   │   │   │   │   ├── business-catalogue.component.spec.ts
│   │   │   │   │   └── business-catalogue.component.ts
│   │   │   │   ├── business-catalogue-item
│   │   │   │   │   ├── business-catalogue-item.component.html
│   │   │   │   │   ├── business-catalogue-item.component.scss
│   │   │   │   │   ├── business-catalogue-item.component.spec.ts
│   │   │   │   │   └── business-catalogue-item.component.ts
│   │   │   │   ├── business-catalogue-list
│   │   │   │   │   ├── business-catalogue-list.component.html
│   │   │   │   │   ├── business-catalogue-list.component.scss
│   │   │   │   │   ├── business-catalogue-list.component.spec.ts
│   │   │   │   │   └── business-catalogue-list.component.ts
│   │   │   │   ├── business-catalogue-raise-ticket
│   │   │   │   │   ├── business-catalogue-raise-ticket.component.html
│   │   │   │   │   ├── business-catalogue-raise-ticket.component.scss
│   │   │   │   │   ├── business-catalogue-raise-ticket.component.spec.ts
│   │   │   │   │   └── business-catalogue-raise-ticket.component.ts
│   │   │   │   ├── business-catalogue-sidebar
│   │   │   │   │   ├── business-catalogue-sidebar.component.html
│   │   │   │   │   ├── business-catalogue-sidebar.component.scss
│   │   │   │   │   ├── business-catalogue-sidebar.component.spec.ts
│   │   │   │   │   └── business-catalogue-sidebar.component.ts
│   │   │   │   └── business-sekeleton
│   │   │   │       ├── business-sekeleton.component.html
│   │   │   │       ├── business-sekeleton.component.scss
│   │   │   │       ├── business-sekeleton.component.spec.ts
│   │   │   │       └── business-sekeleton.component.ts
│   │   │   └── services
│   │   │       └── business-catalogue
│   │   │           ├── business-catalogue.component.html
│   │   │           ├── business-catalogue.component.scss
│   │   │           ├── business-catalogue.component.spec.ts
│   │   │           └── business-catalogue.component.ts
│   │   ├── business_rule
│   │   │   ├── business_rule-routing.module.ts
│   │   │   ├── business_rule.module.ts
│   │   │   ├── components
│   │   │   │   ├── create-new-rule
│   │   │   │   │   ├── create-new-rule.component.html
│   │   │   │   │   ├── create-new-rule.component.scss
│   │   │   │   │   ├── create-new-rule.component.spec.ts
│   │   │   │   │   └── create-new-rule.component.ts
│   │   │   │   ├── rule-grid
│   │   │   │   │   ├── rule-grid.component.html
│   │   │   │   │   ├── rule-grid.component.scss
│   │   │   │   │   ├── rule-grid.component.spec.ts
│   │   │   │   │   └── rule-grid.component.ts
│   │   │   │   ├── rule-list
│   │   │   │   │   ├── rule-list.component.html
│   │   │   │   │   ├── rule-list.component.scss
│   │   │   │   │   ├── rule-list.component.spec.ts
│   │   │   │   │   └── rule-list.component.ts
│   │   │   │   └── rule-sidebar
│   │   │   │       ├── rule-sidebar.component.html
│   │   │   │       ├── rule-sidebar.component.scss
│   │   │   │       ├── rule-sidebar.component.spec.ts
│   │   │   │       └── rule-sidebar.component.ts
│   │   │   └── services
│   │   │       ├── business_rule.service.spec.ts
│   │   │       └── business_rule.service.ts
│   │   ├── ci-relation-rules
│   │   │   ├── ci-relation-rules-routing.module.ts
│   │   │   ├── ci-relation-rules.module.ts
│   │   │   ├── components
│   │   │   │   └── ci-relation-rules
│   │   │   │       ├── ci-relation-rules.component.html
│   │   │   │       ├── ci-relation-rules.component.scss
│   │   │   │       ├── ci-relation-rules.component.spec.ts
│   │   │   │       └── ci-relation-rules.component.ts
│   │   │   └── services
│   │   │       ├── ci-relation-rules.service.spec.ts
│   │   │       └── ci-relation-rules.service.ts
│   │   ├── correlation-rules-configuration
│   │   │   ├── components
│   │   │   │   ├── correlation-card
│   │   │   │   │   ├── correlation-card.component.html
│   │   │   │   │   ├── correlation-card.component.scss
│   │   │   │   │   ├── correlation-card.component.spec.ts
│   │   │   │   │   └── correlation-card.component.ts
│   │   │   │   └── correlation-sidebar
│   │   │   │       ├── correlation-sidebar.component.html
│   │   │   │       ├── correlation-sidebar.component.scss
│   │   │   │       ├── correlation-sidebar.component.spec.ts
│   │   │   │       └── correlation-sidebar.component.ts
│   │   │   ├── correlation-rules-configuration-routing.module.ts
│   │   │   ├── correlation-rules-configuration.module.ts
│   │   │   └── services
│   │   │       ├── correlation-rules.service.spec.ts
│   │   │       └── correlation-rules.service.ts
│   │   ├── customer-registration
│   │   │   ├── components
│   │   │   │   ├── add-customer-registration
│   │   │   │   │   ├── add-customer-registration.component.html
│   │   │   │   │   ├── add-customer-registration.component.scss
│   │   │   │   │   ├── add-customer-registration.component.spec.ts
│   │   │   │   │   └── add-customer-registration.component.ts
│   │   │   │   ├── customer-registration-page
│   │   │   │   │   ├── customer-registration-page.component.html
│   │   │   │   │   ├── customer-registration-page.component.scss
│   │   │   │   │   ├── customer-registration-page.component.spec.ts
│   │   │   │   │   └── customer-registration-page.component.ts
│   │   │   │   └── customer-skeleton
│   │   │   │       ├── customer-skeleton.component.html
│   │   │   │       ├── customer-skeleton.component.scss
│   │   │   │       ├── customer-skeleton.component.spec.ts
│   │   │   │       └── customer-skeleton.component.ts
│   │   │   ├── customer-registration-routing.module.ts
│   │   │   ├── customer-registration.module.ts
│   │   │   └── services
│   │   │       ├── customer-registration.service.spec.ts
│   │   │       └── customer-registration.service.ts
│   │   ├── dashboard
│   │   │   ├── components
│   │   │   │   ├── add-dashboard
│   │   │   │   │   ├── add-dashboard.component.html
│   │   │   │   │   ├── add-dashboard.component.scss
│   │   │   │   │   ├── add-dashboard.component.spec.ts
│   │   │   │   │   └── add-dashboard.component.ts
│   │   │   │   ├── chart
│   │   │   │   │   ├── chart.component.html
│   │   │   │   │   ├── chart.component.scss
│   │   │   │   │   ├── chart.component.spec.ts
│   │   │   │   │   └── chart.component.ts
│   │   │   │   ├── critical-device-summary
│   │   │   │   │   ├── critical-device-summary.component.html
│   │   │   │   │   ├── critical-device-summary.component.scss
│   │   │   │   │   ├── critical-device-summary.component.spec.ts
│   │   │   │   │   └── critical-device-summary.component.ts
│   │   │   │   ├── dashboard
│   │   │   │   │   ├── dashboard.component.html
│   │   │   │   │   ├── dashboard.component.scss
│   │   │   │   │   └── dashboard.component.ts
│   │   │   │   ├── dashboard-configuration
│   │   │   │   │   ├── dashboard-configuration.component.html
│   │   │   │   │   ├── dashboard-configuration.component.scss
│   │   │   │   │   ├── dashboard-configuration.component.spec.ts
│   │   │   │   │   └── dashboard-configuration.component.ts
│   │   │   │   ├── dashboard-grid
│   │   │   │   │   ├── dashboard-grid.component.html
│   │   │   │   │   ├── dashboard-grid.component.scss
│   │   │   │   │   ├── dashboard-grid.component.spec.ts
│   │   │   │   │   └── dashboard-grid.component.ts
│   │   │   │   ├── dashboard-sidebar
│   │   │   │   │   ├── dashboard-sidebar.component.html
│   │   │   │   │   ├── dashboard-sidebar.component.scss
│   │   │   │   │   ├── dashboard-sidebar.component.spec.ts
│   │   │   │   │   └── dashboard-sidebar.component.ts
│   │   │   │   ├── dashboard-slides-config
│   │   │   │   │   ├── dashboard-slides-config.component.html
│   │   │   │   │   ├── dashboard-slides-config.component.scss
│   │   │   │   │   ├── dashboard-slides-config.component.spec.ts
│   │   │   │   │   └── dashboard-slides-config.component.ts
│   │   │   │   ├── dashboard-view
│   │   │   │   │   ├── dashboard-view.component.html
│   │   │   │   │   ├── dashboard-view.component.scss
│   │   │   │   │   ├── dashboard-view.component.spec.ts
│   │   │   │   │   └── dashboard-view.component.ts
│   │   │   │   ├── dns-branch-summary
│   │   │   │   │   ├── dns-branch-summary.component.html
│   │   │   │   │   ├── dns-branch-summary.component.scss
│   │   │   │   │   ├── dns-branch-summary.component.spec.ts
│   │   │   │   │   └── dns-branch-summary.component.ts
│   │   │   │   ├── global-filter-sidebar
│   │   │   │   │   ├── global-filter-sidebar.component.html
│   │   │   │   │   ├── global-filter-sidebar.component.scss
│   │   │   │   │   ├── global-filter-sidebar.component.spec.ts
│   │   │   │   │   └── global-filter-sidebar.component.ts
│   │   │   │   ├── npi-location
│   │   │   │   │   ├── npi-location.component.html
│   │   │   │   │   ├── npi-location.component.scss
│   │   │   │   │   ├── npi-location.component.spec.ts
│   │   │   │   │   └── npi-location.component.ts
│   │   │   │   ├── npi-sidebar
│   │   │   │   │   ├── npi-sidebar.component.html
│   │   │   │   │   ├── npi-sidebar.component.scss
│   │   │   │   │   ├── npi-sidebar.component.spec.ts
│   │   │   │   │   └── npi-sidebar.component.ts
│   │   │   │   ├── npi-widget-dashboard
│   │   │   │   │   ├── npi-widget-dashboard.component.html
│   │   │   │   │   ├── npi-widget-dashboard.component.scss
│   │   │   │   │   ├── npi-widget-dashboard.component.spec.ts
│   │   │   │   │   └── npi-widget-dashboard.component.ts
│   │   │   │   ├── schedule-dashboard
│   │   │   │   │   ├── schedule-dashboard.component.html
│   │   │   │   │   ├── schedule-dashboard.component.scss
│   │   │   │   │   ├── schedule-dashboard.component.spec.ts
│   │   │   │   │   └── schedule-dashboard.component.ts
│   │   │   │   ├── spi_npi-grid-view
│   │   │   │   │   ├── spi_npi-grid-view.component.html
│   │   │   │   │   ├── spi_npi-grid-view.component.scss
│   │   │   │   │   ├── spi_npi-grid-view.component.spec.ts
│   │   │   │   │   └── spi_npi-grid-view.component.ts
│   │   │   │   ├── widget-configuration
│   │   │   │   │   ├── widget-configuration.component.html
│   │   │   │   │   ├── widget-configuration.component.scss
│   │   │   │   │   ├── widget-configuration.component.spec.ts
│   │   │   │   │   └── widget-configuration.component.ts
│   │   │   │   ├── widget-render
│   │   │   │   │   ├── calendar-data-source.ts
│   │   │   │   │   ├── coolTheme.ts
│   │   │   │   │   ├── widget-render.component.html
│   │   │   │   │   ├── widget-render.component.scss
│   │   │   │   │   ├── widget-render.component.spec.ts
│   │   │   │   │   ├── widget-render.component.ts
│   │   │   │   │   └── widget-render.component_bkup.html
│   │   │   │   └── widget-topology-panel
│   │   │   │       ├── widget-topology-panel.component.html
│   │   │   │       ├── widget-topology-panel.component.scss
│   │   │   │       ├── widget-topology-panel.component.spec.ts
│   │   │   │       └── widget-topology-panel.component.ts
│   │   │   ├── dashboard-routing.module.ts
│   │   │   ├── dashboard.module.ts
│   │   │   └── services
│   │   │       ├── dashboard.service.spec.ts
│   │   │       └── dashboard.service.ts
│   │   ├── department
│   │   │   ├── components
│   │   │   │   ├── department
│   │   │   │   │   ├── department.component.html
│   │   │   │   │   ├── department.component.scss
│   │   │   │   │   ├── department.component.spec.ts
│   │   │   │   │   └── department.component.ts
│   │   │   │   ├── department-card
│   │   │   │   │   ├── department-card.component.html
│   │   │   │   │   ├── department-card.component.scss
│   │   │   │   │   ├── department-card.component.spec.ts
│   │   │   │   │   └── department-card.component.ts
│   │   │   │   └── department-grid
│   │   │   │       ├── department-grid.component.html
│   │   │   │       ├── department-grid.component.scss
│   │   │   │       ├── department-grid.component.spec.ts
│   │   │   │       └── department-grid.component.ts
│   │   │   ├── department-routing.module.ts
│   │   │   ├── department.module.ts
│   │   │   └── services
│   │   │       ├── department.service.spec.ts
│   │   │       └── department.service.ts
│   │   ├── dynamic-form
│   │   │   ├── components
│   │   │   │   ├── dynamic-form
│   │   │   │   │   ├── dynamic-form.component.html
│   │   │   │   │   ├── dynamic-form.component.scss
│   │   │   │   │   ├── dynamic-form.component.spec.ts
│   │   │   │   │   └── dynamic-form.component.ts
│   │   │   │   └── form-builder
│   │   │   │       ├── form-builder.component.html
│   │   │   │       ├── form-builder.component.scss
│   │   │   │       ├── form-builder.component.spec.ts
│   │   │   │       └── form-builder.component.ts
│   │   │   ├── dynamic-form-routing.module.ts
│   │   │   ├── dynamic-form.module.ts
│   │   │   ├── global.model.ts
│   │   │   ├── material-module.ts
│   │   │   └── services
│   │   │       ├── dynamic-form.service.spec.ts
│   │   │       └── dynamic-form.service.ts
│   │   ├── email-template
│   │   │   ├── components
│   │   │   │   ├── email-tem.html
│   │   │   │   ├── email-template
│   │   │   │   │   ├── email-template.component.html
│   │   │   │   │   ├── email-template.component.scss
│   │   │   │   │   ├── email-template.component.spec.ts
│   │   │   │   │   └── email-template.component.ts
│   │   │   │   └── email-template-grid
│   │   │   │       ├── email-template-grid.component.html
│   │   │   │       ├── email-template-grid.component.scss
│   │   │   │       ├── email-template-grid.component.spec.ts
│   │   │   │       └── email-template-grid.component.ts
│   │   │   ├── email-template-routing.module.ts
│   │   │   ├── email-template.module.ts
│   │   │   └── services
│   │   │       ├── email-template.service.spec.ts
│   │   │       └── email-template.service.ts
│   │   ├── ems
│   │   │   ├── components
│   │   │   │   ├── ems-card
│   │   │   │   │   ├── ems-card.component.html
│   │   │   │   │   ├── ems-card.component.scss
│   │   │   │   │   ├── ems-card.component.spec.ts
│   │   │   │   │   └── ems-card.component.ts
│   │   │   │   ├── ems-grid
│   │   │   │   │   ├── ems-grid.component.html
│   │   │   │   │   ├── ems-grid.component.scss
│   │   │   │   │   ├── ems-grid.component.spec.ts
│   │   │   │   │   └── ems-grid.component.ts
│   │   │   │   ├── ems-rescan
│   │   │   │   │   ├── ems-rescan.component.html
│   │   │   │   │   ├── ems-rescan.component.scss
│   │   │   │   │   ├── ems-rescan.component.spec.ts
│   │   │   │   │   └── ems-rescan.component.ts
│   │   │   │   └── new-ems-profile
│   │   │   │       ├── new-ems-profile.component.html
│   │   │   │       ├── new-ems-profile.component.scss
│   │   │   │       ├── new-ems-profile.component.spec.ts
│   │   │   │       └── new-ems-profile.component.ts
│   │   │   ├── ems-routing.module.ts
│   │   │   ├── ems.module.ts
│   │   │   └── services
│   │   │       ├── ems-service.service.spec.ts
│   │   │       └── ems-service.service.ts
│   │   ├── escalation
│   │   │   ├── components
│   │   │   │   ├── create-new-team-escalation
│   │   │   │   │   ├── create-new-team-escalation.component.html
│   │   │   │   │   ├── create-new-team-escalation.component.scss
│   │   │   │   │   ├── create-new-team-escalation.component.spec.ts
│   │   │   │   │   └── create-new-team-escalation.component.ts
│   │   │   │   ├── escalation-grid
│   │   │   │   │   ├── escalation-grid.component.html
│   │   │   │   │   ├── escalation-grid.component.scss
│   │   │   │   │   ├── escalation-grid.component.spec.ts
│   │   │   │   │   └── escalation-grid.component.ts
│   │   │   │   ├── escalation-list
│   │   │   │   │   ├── escalation-list.component.html
│   │   │   │   │   ├── escalation-list.component.scss
│   │   │   │   │   ├── escalation-list.component.spec.ts
│   │   │   │   │   └── escalation-list.component.ts
│   │   │   │   ├── escalation-sidebar
│   │   │   │   │   ├── escalation-sidebar.component.html
│   │   │   │   │   ├── escalation-sidebar.component.scss
│   │   │   │   │   ├── escalation-sidebar.component.spec.ts
│   │   │   │   │   └── escalation-sidebar.component.ts
│   │   │   │   └── view-escalation-sidebar
│   │   │   │       ├── view-escalation-sidebar.component.html
│   │   │   │       ├── view-escalation-sidebar.component.scss
│   │   │   │       ├── view-escalation-sidebar.component.spec.ts
│   │   │   │       └── view-escalation-sidebar.component.ts
│   │   │   ├── escalation-routing.module.ts
│   │   │   ├── escalation.module.ts
│   │   │   └── services
│   │   │       ├── escalation.service.spec.ts
│   │   │       └── escalation.service.ts
│   │   ├── events
│   │   │   ├── components
│   │   │   │   ├── action-sidebar
│   │   │   │   │   ├── action-sidebar.component.html
│   │   │   │   │   ├── action-sidebar.component.scss
│   │   │   │   │   ├── action-sidebar.component.spec.ts
│   │   │   │   │   └── action-sidebar.component.ts
│   │   │   │   ├── activity-log
│   │   │   │   │   ├── activity-log.component.html
│   │   │   │   │   ├── activity-log.component.scss
│   │   │   │   │   ├── activity-log.component.spec.ts
│   │   │   │   │   └── activity-log.component.ts
│   │   │   │   ├── assign-events
│   │   │   │   │   ├── assign-events.component.html
│   │   │   │   │   ├── assign-events.component.scss
│   │   │   │   │   ├── assign-events.component.spec.ts
│   │   │   │   │   └── assign-events.component.ts
│   │   │   │   ├── diagnose-details
│   │   │   │   │   ├── diagnose-details.component.html
│   │   │   │   │   ├── diagnose-details.component.scss
│   │   │   │   │   ├── diagnose-details.component.spec.ts
│   │   │   │   │   └── diagnose-details.component.ts
│   │   │   │   ├── event-details
│   │   │   │   │   ├── event-details.component.html
│   │   │   │   │   ├── event-details.component.scss
│   │   │   │   │   ├── event-details.component.spec.ts
│   │   │   │   │   └── event-details.component.ts
│   │   │   │   ├── event-due-date
│   │   │   │   │   ├── event-due-date.component.html
│   │   │   │   │   ├── event-due-date.component.scss
│   │   │   │   │   ├── event-due-date.component.spec.ts
│   │   │   │   │   └── event-due-date.component.ts
│   │   │   │   ├── event-grid
│   │   │   │   │   ├── event-grid.component.html
│   │   │   │   │   ├── event-grid.component.scss
│   │   │   │   │   ├── event-grid.component.spec.ts
│   │   │   │   │   └── event-grid.component.ts
│   │   │   │   ├── event-sekeleton
│   │   │   │   │   ├── event-sekeleton.component.html
│   │   │   │   │   ├── event-sekeleton.component.scss
│   │   │   │   │   ├── event-sekeleton.component.spec.ts
│   │   │   │   │   └── event-sekeleton.component.ts
│   │   │   │   ├── events
│   │   │   │   │   ├── events.component.html
│   │   │   │   │   ├── events.component.scss
│   │   │   │   │   ├── events.component.spec.ts
│   │   │   │   │   └── events.component.ts
│   │   │   │   ├── events-third-party-inci
│   │   │   │   │   ├── events-third-party-inci.component.html
│   │   │   │   │   ├── events-third-party-inci.component.scss
│   │   │   │   │   ├── events-third-party-inci.component.spec.ts
│   │   │   │   │   └── events-third-party-inci.component.ts
│   │   │   │   ├── impacted-assets
│   │   │   │   │   ├── impacted-assets.component.html
│   │   │   │   │   ├── impacted-assets.component.scss
│   │   │   │   │   ├── impacted-assets.component.spec.ts
│   │   │   │   │   └── impacted-assets.component.ts
│   │   │   │   └── tag-events
│   │   │   │       ├── tag-events.component.html
│   │   │   │       ├── tag-events.component.scss
│   │   │   │       ├── tag-events.component.spec.ts
│   │   │   │       └── tag-events.component.ts
│   │   │   ├── events-routing.module.ts
│   │   │   ├── events.module.ts
│   │   │   └── services
│   │   │       ├── events.service.spec.ts
│   │   │       └── events.service.ts
│   │   ├── external
│   │   │   ├── components
│   │   │   │   ├── ci-allocate
│   │   │   │   │   ├── ci-allocate.component.html
│   │   │   │   │   ├── ci-allocate.component.scss
│   │   │   │   │   ├── ci-allocate.component.spec.ts
│   │   │   │   │   └── ci-allocate.component.ts
│   │   │   │   ├── ci-deallocate
│   │   │   │   │   ├── ci-deallocate.component.html
│   │   │   │   │   ├── ci-deallocate.component.scss
│   │   │   │   │   ├── ci-deallocate.component.spec.ts
│   │   │   │   │   └── ci-deallocate.component.ts
│   │   │   │   ├── google-configuration
│   │   │   │   │   ├── google-signin.component.html
│   │   │   │   │   ├── google-signin.component.scss
│   │   │   │   │   ├── google-signin.component.spec.ts
│   │   │   │   │   └── google-signin.component.ts
│   │   │   │   ├── inf-approval
│   │   │   │   │   ├── inf-approval.component.html
│   │   │   │   │   ├── inf-approval.component.scss
│   │   │   │   │   ├── inf-approval.component.spec.ts
│   │   │   │   │   └── inf-approval.component.ts
│   │   │   │   ├── microsoft-signin
│   │   │   │   │   ├── microsoft-signin.component.html
│   │   │   │   │   ├── microsoft-signin.component.scss
│   │   │   │   │   ├── microsoft-signin.component.spec.ts
│   │   │   │   │   └── microsoft-signin.component.ts
│   │   │   │   ├── requester-reg
│   │   │   │   │   ├── requester-reg.component.html
│   │   │   │   │   ├── requester-reg.component.scss
│   │   │   │   │   ├── requester-reg.component.spec.ts
│   │   │   │   │   └── requester-reg.component.ts
│   │   │   │   └── user-reg
│   │   │   │       ├── user-reg.component.html
│   │   │   │       ├── user-reg.component.scss
│   │   │   │       ├── user-reg.component.spec.ts
│   │   │   │       └── user-reg.component.ts
│   │   │   ├── external-routing.module.ts
│   │   │   ├── external.module.ts
│   │   │   └── services
│   │   │       ├── external.service.spec.ts
│   │   │       └── external.service.ts
│   │   ├── field-configuration
│   │   │   ├── components
│   │   │   │   ├── field-config
│   │   │   │   │   ├── field-config.component.html
│   │   │   │   │   ├── field-config.component.scss
│   │   │   │   │   ├── field-config.component.spec.ts
│   │   │   │   │   └── field-config.component.ts
│   │   │   │   └── field-config-list
│   │   │   │       ├── field-config-list.component.html
│   │   │   │       ├── field-config-list.component.scss
│   │   │   │       ├── field-config-list.component.spec.ts
│   │   │   │       └── field-config-list.component.ts
│   │   │   ├── field-configuration-routing.module.ts
│   │   │   ├── field-configuration.module.ts
│   │   │   └── services
│   │   │       ├── configuration.service.spec.ts
│   │   │       └── configuration.service.ts
│   │   ├── geomap
│   │   │   ├── components
│   │   │   │   └── geo-map-view
│   │   │   │       ├── geo-map-view.component.html
│   │   │   │       ├── geo-map-view.component.scss
│   │   │   │       ├── geo-map-view.component.spec.ts
│   │   │   │       └── geo-map-view.component.ts
│   │   │   ├── geomap-routing.module.ts
│   │   │   ├── geomap.module.ts
│   │   │   └── services
│   │   │       ├── geo-map-view.service.spec.ts
│   │   │       └── geo-map-view.service.ts
│   │   ├── get-started
│   │   │   ├── components
│   │   │   │   ├── email-preview
│   │   │   │   │   ├── email-preview.component.html
│   │   │   │   │   ├── email-preview.component.scss
│   │   │   │   │   ├── email-preview.component.spec.ts
│   │   │   │   │   └── email-preview.component.ts
│   │   │   │   ├── home
│   │   │   │   │   ├── home.component.html
│   │   │   │   │   ├── home.component.scss
│   │   │   │   │   ├── home.component.spec.ts
│   │   │   │   │   └── home.component.ts
│   │   │   │   ├── invite-agents
│   │   │   │   │   ├── invite-agents.component.html
│   │   │   │   │   ├── invite-agents.component.scss
│   │   │   │   │   ├── invite-agents.component.spec.ts
│   │   │   │   │   └── invite-agents.component.ts
│   │   │   │   └── report
│   │   │   │       ├── report.component.html
│   │   │   │       ├── report.component.scss
│   │   │   │       ├── report.component.spec.ts
│   │   │   │       └── report.component.ts
│   │   │   ├── get-started-routing.module.ts
│   │   │   ├── get-started.module.ts
│   │   │   └── services
│   │   │       ├── get-started.service.spec.ts
│   │   │       └── get-started.service.ts
│   │   ├── imap-configuration
│   │   │   ├── components
│   │   │   │   ├── imap-configuration
│   │   │   │   │   ├── imap-configuration.component.html
│   │   │   │   │   ├── imap-configuration.component.scss
│   │   │   │   │   ├── imap-configuration.component.spec.ts
│   │   │   │   │   └── imap-configuration.component.ts
│   │   │   │   ├── imap-configuration-card
│   │   │   │   │   ├── imap-configuration-card.component.html
│   │   │   │   │   ├── imap-configuration-card.component.scss
│   │   │   │   │   ├── imap-configuration-card.component.spec.ts
│   │   │   │   │   └── imap-configuration-card.component.ts
│   │   │   │   └── imap-configuration-grid
│   │   │   │       ├── imap-configuration-grid.component.html
│   │   │   │       ├── imap-configuration-grid.component.scss
│   │   │   │       ├── imap-configuration-grid.component.spec.ts
│   │   │   │       └── imap-configuration-grid.component.ts
│   │   │   ├── imap-configuration-routing.module.ts
│   │   │   ├── imap-configuration.module.ts
│   │   │   └── services
│   │   │       ├── imap-configuration.service.spec.ts
│   │   │       └── imap-configuration.service.ts
│   │   ├── infraon-configuration
│   │   │   ├── components
│   │   │   │   ├── configuration
│   │   │   │   │   ├── configuration.component.html
│   │   │   │   │   ├── configuration.component.scss
│   │   │   │   │   ├── configuration.component.spec.ts
│   │   │   │   │   └── configuration.component.ts
│   │   │   │   ├── configuration-list
│   │   │   │   │   ├── configuration-list.component.html
│   │   │   │   │   ├── configuration-list.component.scss
│   │   │   │   │   ├── configuration-list.component.spec.ts
│   │   │   │   │   └── configuration-list.component.ts
│   │   │   │   └── configuration-sidebar
│   │   │   │       ├── configuration-sidebar.component.html
│   │   │   │       ├── configuration-sidebar.component.scss
│   │   │   │       ├── configuration-sidebar.component.spec.ts
│   │   │   │       └── configuration-sidebar.component.ts
│   │   │   ├── infraon-configuration-routing.module.ts
│   │   │   └── infraon-configuration.module.ts
│   │   ├── infraon-url
│   │   │   ├── components
│   │   │   │   └── infraon-url
│   │   │   │       ├── infraon-url.component.html
│   │   │   │       ├── infraon-url.component.scss
│   │   │   │       ├── infraon-url.component.spec.ts
│   │   │   │       └── infraon-url.component.ts
│   │   │   ├── infraon-url-routing.module.ts
│   │   │   ├── infraon-url.module.ts
│   │   │   ├── infraon-url.service.spec.ts
│   │   │   └── infraon-url.service.ts
│   │   ├── job-progress
│   │   │   ├── components
│   │   │   │   ├── job-info-sidebar
│   │   │   │   │   ├── job-info-sidebar.component.html
│   │   │   │   │   ├── job-info-sidebar.component.scss
│   │   │   │   │   ├── job-info-sidebar.component.spec.ts
│   │   │   │   │   └── job-info-sidebar.component.ts
│   │   │   │   └── job-progress
│   │   │   │       ├── job-progress.component.html
│   │   │   │       ├── job-progress.component.scss
│   │   │   │       ├── job-progress.component.spec.ts
│   │   │   │       └── job-progress.component.ts
│   │   │   ├── job-progress-routing.module.ts
│   │   │   ├── job-progress.module.ts
│   │   │   └── services
│   │   │       ├── job-progress.service.spec.ts
│   │   │       └── job-progress.service.ts
│   │   ├── knowledge-base
│   │   │   ├── components
│   │   │   │   ├── add-attachment
│   │   │   │   │   ├── add-attachment.component.html
│   │   │   │   │   ├── add-attachment.component.scss
│   │   │   │   │   ├── add-attachment.component.spec.ts
│   │   │   │   │   └── add-attachment.component.ts
│   │   │   │   ├── kb-add
│   │   │   │   │   ├── kb-add.component.html
│   │   │   │   │   ├── kb-add.component.scss
│   │   │   │   │   ├── kb-add.component.spec.ts
│   │   │   │   │   └── kb-add.component.ts
│   │   │   │   ├── kb-detail
│   │   │   │   │   ├── kb-detail.component.html
│   │   │   │   │   ├── kb-detail.component.scss
│   │   │   │   │   ├── kb-detail.component.spec.ts
│   │   │   │   │   └── kb-detail.component.ts
│   │   │   │   ├── kb-edit
│   │   │   │   │   ├── kb-edit.component.html
│   │   │   │   │   ├── kb-edit.component.scss
│   │   │   │   │   ├── kb-edit.component.spec.ts
│   │   │   │   │   └── kb-edit.component.ts
│   │   │   │   ├── kb-history
│   │   │   │   │   ├── kb-history.component.html
│   │   │   │   │   ├── kb-history.component.scss
│   │   │   │   │   ├── kb-history.component.spec.ts
│   │   │   │   │   └── kb-history.component.ts
│   │   │   │   ├── kb-list
│   │   │   │   │   ├── kb-list.component.html
│   │   │   │   │   ├── kb-list.component.scss
│   │   │   │   │   ├── kb-list.component.spec.ts
│   │   │   │   │   └── kb-list.component.ts
│   │   │   │   ├── kb-ratings
│   │   │   │   │   ├── kb-ratings.component.html
│   │   │   │   │   ├── kb-ratings.component.scss
│   │   │   │   │   ├── kb-ratings.component.spec.ts
│   │   │   │   │   └── kb-ratings.component.ts
│   │   │   │   ├── kb-sekeleton
│   │   │   │   │   ├── kb-sekeleton.component.html
│   │   │   │   │   ├── kb-sekeleton.component.scss
│   │   │   │   │   ├── kb-sekeleton.component.spec.ts
│   │   │   │   │   └── kb-sekeleton.component.ts
│   │   │   │   └── kb-views
│   │   │   │       ├── kb-views.component.html
│   │   │   │       ├── kb-views.component.scss
│   │   │   │       ├── kb-views.component.spec.ts
│   │   │   │       └── kb-views.component.ts
│   │   │   ├── knowledge-base-routing.module.ts
│   │   │   ├── knowledge-base.module.ts
│   │   │   ├── services
│   │   │   │   ├── kb.service.spec.ts
│   │   │   │   └── kb.service.ts
│   │   │   └── types
│   │   │       └── kb-type.ts
│   │   ├── leaves
│   │   │   ├── components
│   │   │   │   ├── leave-config
│   │   │   │   │   ├── leave-config.component.html
│   │   │   │   │   ├── leave-config.component.scss
│   │   │   │   │   ├── leave-config.component.spec.ts
│   │   │   │   │   └── leave-config.component.ts
│   │   │   │   ├── leave-slider
│   │   │   │   │   ├── leave-slider.component.html
│   │   │   │   │   ├── leave-slider.component.scss
│   │   │   │   │   ├── leave-slider.component.spec.ts
│   │   │   │   │   └── leave-slider.component.ts
│   │   │   │   ├── leaves
│   │   │   │   │   ├── leaves.component.html
│   │   │   │   │   ├── leaves.component.scss
│   │   │   │   │   ├── leaves.component.spec.ts
│   │   │   │   │   └── leaves.component.ts
│   │   │   │   └── leaves-list
│   │   │   │       ├── leaves-list.component.html
│   │   │   │       ├── leaves-list.component.scss
│   │   │   │       ├── leaves-list.component.spec.ts
│   │   │   │       └── leaves-list.component.ts
│   │   │   ├── leaves-routing.module.ts
│   │   │   └── leaves.module.ts
│   │   ├── license
│   │   │   ├── components
│   │   │   │   └── license-upload
│   │   │   │       ├── license-upload.component.html
│   │   │   │       ├── license-upload.component.scss
│   │   │   │       ├── license-upload.component.spec.ts
│   │   │   │       └── license-upload.component.ts
│   │   │   ├── license-routing.module.ts
│   │   │   └── license.module.ts
│   │   ├── messenger-audit
│   │   │   ├── components
│   │   │   │   ├── messanger-outgoing-message-list
│   │   │   │   │   ├── messanger-outgoing-message-list.component.html
│   │   │   │   │   ├── messanger-outgoing-message-list.component.scss
│   │   │   │   │   ├── messanger-outgoing-message-list.component.spec.ts
│   │   │   │   │   └── messanger-outgoing-message-list.component.ts
│   │   │   │   ├── messenger-audit
│   │   │   │   │   ├── messenger-audit.component.html
│   │   │   │   │   ├── messenger-audit.component.scss
│   │   │   │   │   ├── messenger-audit.component.spec.ts
│   │   │   │   │   └── messenger-audit.component.ts
│   │   │   │   ├── messenger-audit-api-details
│   │   │   │   │   ├── messenger-audit-api-details.component.html
│   │   │   │   │   ├── messenger-audit-api-details.component.scss
│   │   │   │   │   ├── messenger-audit-api-details.component.spec.ts
│   │   │   │   │   └── messenger-audit-api-details.component.ts
│   │   │   │   ├── messenger-audit-api-list-item
│   │   │   │   │   ├── messenger-audit-api-list-item.component.html
│   │   │   │   │   ├── messenger-audit-api-list-item.component.scss
│   │   │   │   │   ├── messenger-audit-api-list-item.component.spec.ts
│   │   │   │   │   └── messenger-audit-api-list-item.component.ts
│   │   │   │   ├── messenger-audit-compose
│   │   │   │   │   ├── messenger-audit-compose.component.html
│   │   │   │   │   ├── messenger-audit-compose.component.scss
│   │   │   │   │   ├── messenger-audit-compose.component.spec.ts
│   │   │   │   │   └── messenger-audit-compose.component.ts
│   │   │   │   ├── messenger-audit-details
│   │   │   │   │   ├── messenger-audit-details.component.html
│   │   │   │   │   ├── messenger-audit-details.component.scss
│   │   │   │   │   ├── messenger-audit-details.component.spec.ts
│   │   │   │   │   └── messenger-audit-details.component.ts
│   │   │   │   ├── messenger-audit-list
│   │   │   │   │   ├── messenger-audit-list.component.html
│   │   │   │   │   ├── messenger-audit-list.component.scss
│   │   │   │   │   ├── messenger-audit-list.component.spec.ts
│   │   │   │   │   └── messenger-audit-list.component.ts
│   │   │   │   ├── messenger-audit-list-item
│   │   │   │   │   ├── messenger-audit-list-item.component.html
│   │   │   │   │   ├── messenger-audit-list-item.component.scss
│   │   │   │   │   ├── messenger-audit-list-item.component.spec.ts
│   │   │   │   │   └── messenger-audit-list-item.component.ts
│   │   │   │   ├── messenger-audit-sidebar
│   │   │   │   │   ├── messenger-audit-sidebar.component.html
│   │   │   │   │   ├── messenger-audit-sidebar.component.scss
│   │   │   │   │   ├── messenger-audit-sidebar.component.spec.ts
│   │   │   │   │   └── messenger-audit-sidebar.component.ts
│   │   │   │   ├── messenger-audit-sms-details
│   │   │   │   │   ├── messenger-audit-sms-details.component.html
│   │   │   │   │   ├── messenger-audit-sms-details.component.scss
│   │   │   │   │   ├── messenger-audit-sms-details.component.spec.ts
│   │   │   │   │   └── messenger-audit-sms-details.component.ts
│   │   │   │   ├── messenger-audit-sms-list-item
│   │   │   │   │   ├── messenger-audit-sms-list-item.component.html
│   │   │   │   │   ├── messenger-audit-sms-list-item.component.scss
│   │   │   │   │   ├── messenger-audit-sms-list-item.component.spec.ts
│   │   │   │   │   └── messenger-audit-sms-list-item.component.ts
│   │   │   │   └── messenger-sekeleton
│   │   │   │       ├── messenger-sekeleton.component.html
│   │   │   │       ├── messenger-sekeleton.component.scss
│   │   │   │       ├── messenger-sekeleton.component.spec.ts
│   │   │   │       └── messenger-sekeleton.component.ts
│   │   │   ├── messenger-audit-routing.module.ts
│   │   │   ├── messenger-audit-service.ts
│   │   │   ├── messenger-audit.module.ts
│   │   │   └── services
│   │   │       ├── messenger.service.spec.ts
│   │   │       └── messenger.service.ts
│   │   ├── metric
│   │   │   ├── components
│   │   │   │   ├── metric
│   │   │   │   │   ├── metric.component.html
│   │   │   │   │   ├── metric.component.scss
│   │   │   │   │   ├── metric.component.spec.ts
│   │   │   │   │   └── metric.component.ts
│   │   │   │   ├── metric-edit
│   │   │   │   │   ├── metric-edit.component.html
│   │   │   │   │   ├── metric-edit.component.scss
│   │   │   │   │   ├── metric-edit.component.spec.ts
│   │   │   │   │   └── metric-edit.component.ts
│   │   │   │   └── metric-grid
│   │   │   │       ├── metric-grid.component.html
│   │   │   │       ├── metric-grid.component.scss
│   │   │   │       ├── metric-grid.component.spec.ts
│   │   │   │       └── metric-grid.component.ts
│   │   │   ├── metric-routing.module.ts
│   │   │   ├── metric.module.ts
│   │   │   ├── services
│   │   │   │   ├── metric.service.spec.ts
│   │   │   │   └── metric.service.ts
│   │   │   └── types
│   │   │       └── metric.ts
│   │   ├── miscellaneous
│   │   │   ├── error
│   │   │   │   ├── error.component.html
│   │   │   │   ├── error.component.scss
│   │   │   │   └── error.component.ts
│   │   │   ├── miscellaneous-routing.module.ts
│   │   │   ├── miscellaneous.module.ts
│   │   │   └── not-authorized
│   │   │       ├── not-authorized.component.html
│   │   │       ├── not-authorized.component.scss
│   │   │       └── not-authorized.component.ts
│   │   ├── myleaves
│   │   │   ├── components
│   │   │   │   ├── myleaves
│   │   │   │   │   ├── myleaves.component.html
│   │   │   │   │   ├── myleaves.component.scss
│   │   │   │   │   ├── myleaves.component.spec.ts
│   │   │   │   │   └── myleaves.component.ts
│   │   │   │   ├── myleaves-add
│   │   │   │   │   ├── myleaves-add.component.html
│   │   │   │   │   ├── myleaves-add.component.scss
│   │   │   │   │   └── myleaves-add.component.ts
│   │   │   │   └── myleaves-sekeleton
│   │   │   │       ├── myleaves-sekeleton.component.html
│   │   │   │       ├── myleaves-sekeleton.component.scss
│   │   │   │       ├── myleaves-sekeleton.component.spec.ts
│   │   │   │       └── myleaves-sekeleton.component.ts
│   │   │   ├── myleaves-routing.module.ts
│   │   │   ├── myleaves.module.ts
│   │   │   └── services
│   │   │       ├── myleaves.service.spec.ts
│   │   │       └── myleaves.service.ts
│   │   ├── network-diagram
│   │   │   ├── components
│   │   │   │   ├── network-diagram-grid
│   │   │   │   │   ├── network-diagram-grid.component.html
│   │   │   │   │   ├── network-diagram-grid.component.scss
│   │   │   │   │   ├── network-diagram-grid.component.spec.ts
│   │   │   │   │   └── network-diagram-grid.component.ts
│   │   │   │   └── network-diagram-view
│   │   │   │       ├── network-diagram-view.component.html
│   │   │   │       ├── network-diagram-view.component.scss
│   │   │   │       ├── network-diagram-view.component.spec.ts
│   │   │   │       └── network-diagram-view.component.ts
│   │   │   ├── network-diagram-routing.module.ts
│   │   │   ├── network-diagram.module.ts
│   │   │   └── services
│   │   │       ├── network-diagram.service.spec.ts
│   │   │       └── network-diagram.service.ts
│   │   ├── notification
│   │   │   ├── components
│   │   │   │   ├── notification
│   │   │   │   │   ├── notification.component.html
│   │   │   │   │   ├── notification.component.scss
│   │   │   │   │   ├── notification.component.spec.ts
│   │   │   │   │   └── notification.component.ts
│   │   │   │   └── notification-grid
│   │   │   │       ├── notification-grid.component.html
│   │   │   │       ├── notification-grid.component.scss
│   │   │   │       ├── notification-grid.component.spec.ts
│   │   │   │       └── notification-grid.component.ts
│   │   │   ├── notification-routing.module.ts
│   │   │   └── notification.module.ts
│   │   ├── notify-rules
│   │   │   ├── components
│   │   │   │   ├── notify-add
│   │   │   │   │   ├── notify-add.component.html
│   │   │   │   │   ├── notify-add.component.scss
│   │   │   │   │   ├── notify-add.component.spec.ts
│   │   │   │   │   └── notify-add.component.ts
│   │   │   │   ├── notify-email
│   │   │   │   │   ├── notify-email.component.html
│   │   │   │   │   ├── notify-email.component.scss
│   │   │   │   │   ├── notify-email.component.spec.ts
│   │   │   │   │   └── notify-email.component.ts
│   │   │   │   └── notify-rules
│   │   │   │       ├── notify-rules.component.html
│   │   │   │       ├── notify-rules.component.scss
│   │   │   │       ├── notify-rules.component.spec.ts
│   │   │   │       └── notify-rules.component.ts
│   │   │   ├── notify-rules-routing.module.ts
│   │   │   ├── notify-rules.module.ts
│   │   │   └── services
│   │   │       ├── notify-rulles.service.spec.ts
│   │   │       └── notify-rulles.service.ts
│   │   ├── org-setting
│   │   │   ├── components
│   │   │   │   ├── org-setting
│   │   │   │   │   ├── org-setting.component.html
│   │   │   │   │   ├── org-setting.component.scss
│   │   │   │   │   ├── org-setting.component.spec.ts
│   │   │   │   │   └── org-setting.component.ts
│   │   │   │   └── sms-config
│   │   │   │       ├── sms-config.component.html
│   │   │   │       ├── sms-config.component.scss
│   │   │   │       ├── sms-config.component.spec.ts
│   │   │   │       └── sms-config.component.ts
│   │   │   ├── org-setting-routing.module.ts
│   │   │   ├── org-setting.module.ts
│   │   │   └── services
│   │   │       ├── org-setting.service.spec.ts
│   │   │       └── org-setting.service.ts
│   │   ├── organization
│   │   │   ├── components
│   │   │   │   ├── csv-import-location
│   │   │   │   │   ├── csv-import-location.component.html
│   │   │   │   │   ├── csv-import-location.component.scss
│   │   │   │   │   ├── csv-import-location.component.spec.ts
│   │   │   │   │   └── csv-import-location.component.ts
│   │   │   │   ├── csv-location-edit
│   │   │   │   │   ├── csv-location-edit.component.html
│   │   │   │   │   ├── csv-location-edit.component.scss
│   │   │   │   │   ├── csv-location-edit.component.spec.ts
│   │   │   │   │   └── csv-location-edit.component.ts
│   │   │   │   ├── license
│   │   │   │   │   ├── license.component.html
│   │   │   │   │   ├── license.component.scss
│   │   │   │   │   ├── license.component.spec.ts
│   │   │   │   │   └── license.component.ts
│   │   │   │   ├── license-skeleton
│   │   │   │   │   ├── license-skeleton.component.html
│   │   │   │   │   ├── license-skeleton.component.scss
│   │   │   │   │   ├── license-skeleton.component.spec.ts
│   │   │   │   │   └── license-skeleton.component.ts
│   │   │   │   ├── location
│   │   │   │   │   ├── location.component.html
│   │   │   │   │   ├── location.component.scss
│   │   │   │   │   ├── location.component.spec.ts
│   │   │   │   │   └── location.component.ts
│   │   │   │   ├── location-bulk-delete
│   │   │   │   │   ├── location-bulk-delete.component.html
│   │   │   │   │   ├── location-bulk-delete.component.scss
│   │   │   │   │   ├── location-bulk-delete.component.spec.ts
│   │   │   │   │   └── location-bulk-delete.component.ts
│   │   │   │   ├── location-card
│   │   │   │   │   ├── location-card.component.html
│   │   │   │   │   ├── location-card.component.scss
│   │   │   │   │   ├── location-card.component.spec.ts
│   │   │   │   │   └── location-card.component.ts
│   │   │   │   ├── location-sekeleton
│   │   │   │   │   ├── location-sekeleton.component.html
│   │   │   │   │   ├── location-sekeleton.component.scss
│   │   │   │   │   ├── location-sekeleton.component.spec.ts
│   │   │   │   │   └── location-sekeleton.component.ts
│   │   │   │   └── location-update
│   │   │   │       ├── location-update.component.html
│   │   │   │       ├── location-update.component.scss
│   │   │   │       ├── location-update.component.spec.ts
│   │   │   │       └── location-update.component.ts
│   │   │   ├── organization-routing.module.ts
│   │   │   ├── organization.module.ts
│   │   │   └── services
│   │   │       ├── organization.service.spec.ts
│   │   │       └── organization.service.ts
│   │   ├── policy
│   │   │   ├── components
│   │   │   │   ├── password-policy
│   │   │   │   │   ├── password-policy.component.html
│   │   │   │   │   ├── password-policy.component.scss
│   │   │   │   │   ├── password-policy.component.spec.ts
│   │   │   │   │   └── password-policy.component.ts
│   │   │   │   ├── password-policy-card
│   │   │   │   │   ├── password-policy-card.component.html
│   │   │   │   │   ├── password-policy-card.component.scss
│   │   │   │   │   ├── password-policy-card.component.spec.ts
│   │   │   │   │   └── password-policy-card.component.ts
│   │   │   │   └── password-policy-grid
│   │   │   │       ├── password-policy-grid.component.html
│   │   │   │       ├── password-policy-grid.component.scss
│   │   │   │       ├── password-policy-grid.component.spec.ts
│   │   │   │       └── password-policy-grid.component.ts
│   │   │   ├── policy-routing.module.ts
│   │   │   ├── policy.module.ts
│   │   │   └── services
│   │   │       ├── policy.service.spec.ts
│   │   │       └── policy.service.ts
│   │   ├── redirect
│   │   │   ├── components
│   │   │   │   ├── admin-redirection
│   │   │   │   │   ├── admin-redirection.component.html
│   │   │   │   │   ├── admin-redirection.component.scss
│   │   │   │   │   ├── admin-redirection.component.spec.ts
│   │   │   │   │   └── admin-redirection.component.ts
│   │   │   │   └── instance-redirection
│   │   │   │       ├── instance-redirection.component.html
│   │   │   │       ├── instance-redirection.component.scss
│   │   │   │       ├── instance-redirection.component.spec.ts
│   │   │   │       └── instance-redirection.component.ts
│   │   │   ├── redirect-routing.module.ts
│   │   │   ├── redirect.module.ts
│   │   │   └── services
│   │   │       ├── admin.auth.posts.resolve.ts
│   │   │       ├── redirect.service.spec.ts
│   │   │       └── redirect.service.ts
│   │   ├── reports
│   │   │   ├── components
│   │   │   │   ├── adhoc-report
│   │   │   │   │   ├── adhoc-report.component.html
│   │   │   │   │   ├── adhoc-report.component.scss
│   │   │   │   │   ├── adhoc-report.component.spec.ts
│   │   │   │   │   └── adhoc-report.component.ts
│   │   │   │   ├── config-report
│   │   │   │   │   ├── config-report.component.html
│   │   │   │   │   ├── config-report.component.scss
│   │   │   │   │   ├── config-report.component.spec.ts
│   │   │   │   │   └── config-report.component.ts
│   │   │   │   ├── config-report-list
│   │   │   │   │   ├── config-report-list.component.html
│   │   │   │   │   ├── config-report-list.component.scss
│   │   │   │   │   ├── config-report-list.component.spec.ts
│   │   │   │   │   └── config-report-list.component.ts
│   │   │   │   ├── config-report-sidebar
│   │   │   │   │   ├── config-report-sidebar.component.html
│   │   │   │   │   ├── config-report-sidebar.component.scss
│   │   │   │   │   ├── config-report-sidebar.component.spec.ts
│   │   │   │   │   └── config-report-sidebar.component.ts
│   │   │   │   ├── mrtg-report-add
│   │   │   │   │   ├── mrtg-report-add.component.html
│   │   │   │   │   ├── mrtg-report-add.component.scss
│   │   │   │   │   ├── mrtg-report-add.component.spec.ts
│   │   │   │   │   └── mrtg-report-add.component.ts
│   │   │   │   ├── mrtg-report-view
│   │   │   │   │   ├── mrtg-report-view.component.html
│   │   │   │   │   ├── mrtg-report-view.component.scss
│   │   │   │   │   ├── mrtg-report-view.component.spec.ts
│   │   │   │   │   └── mrtg-report-view.component.ts
│   │   │   │   ├── report-add
│   │   │   │   │   ├── filter.pipe.ts
│   │   │   │   │   ├── report-add.component.html
│   │   │   │   │   ├── report-add.component.scss
│   │   │   │   │   ├── report-add.component.spec.ts
│   │   │   │   │   └── report-add.component.ts
│   │   │   │   ├── report-grid
│   │   │   │   │   ├── report-grid.component.html
│   │   │   │   │   ├── report-grid.component.scss
│   │   │   │   │   ├── report-grid.component.spec.ts
│   │   │   │   │   └── report-grid.component.ts
│   │   │   │   ├── report-widget
│   │   │   │   │   ├── report-widget.component.html
│   │   │   │   │   ├── report-widget.component.scss
│   │   │   │   │   ├── report-widget.component.spec.ts
│   │   │   │   │   └── report-widget.component.ts
│   │   │   │   ├── schedule-report
│   │   │   │   │   ├── schedule-report.component.html
│   │   │   │   │   ├── schedule-report.component.scss
│   │   │   │   │   ├── schedule-report.component.spec.ts
│   │   │   │   │   └── schedule-report.component.ts
│   │   │   │   ├── view-report
│   │   │   │   │   ├── view-report.component.html
│   │   │   │   │   ├── view-report.component.scss
│   │   │   │   │   ├── view-report.component.spec.ts
│   │   │   │   │   └── view-report.component.ts
│   │   │   │   ├── view-report-list
│   │   │   │   │   ├── view-report-list.component.html
│   │   │   │   │   ├── view-report-list.component.scss
│   │   │   │   │   ├── view-report-list.component.spec.ts
│   │   │   │   │   └── view-report-list.component.ts
│   │   │   │   └── view-report-sidebar
│   │   │   │       ├── view-report-sidebar.component.html
│   │   │   │       ├── view-report-sidebar.component.scss
│   │   │   │       ├── view-report-sidebar.component.spec.ts
│   │   │   │       └── view-report-sidebar.component.ts
│   │   │   ├── reports-routing.module.ts
│   │   │   ├── reports.module.ts
│   │   │   └── services
│   │   │       ├── reports.service.spec.ts
│   │   │       └── reports.service.ts
│   │   ├── requester
│   │   │   ├── components
│   │   │   │   ├── csv-import-requester
│   │   │   │   │   ├── csv-import-requester.component.html
│   │   │   │   │   ├── csv-import-requester.component.scss
│   │   │   │   │   ├── csv-import-requester.component.spec.ts
│   │   │   │   │   └── csv-import-requester.component.ts
│   │   │   │   ├── csv-requester-edit
│   │   │   │   │   ├── csv-requester-edit.component.html
│   │   │   │   │   ├── csv-requester-edit.component.scss
│   │   │   │   │   ├── csv-requester-edit.component.spec.ts
│   │   │   │   │   └── csv-requester-edit.component.ts
│   │   │   │   ├── invite-requester-grid
│   │   │   │   │   ├── invite-requester-grid.component.html
│   │   │   │   │   ├── invite-requester-grid.component.scss
│   │   │   │   │   ├── invite-requester-grid.component.spec.ts
│   │   │   │   │   └── invite-requester-grid.component.ts
│   │   │   │   ├── invite-requesters
│   │   │   │   │   ├── invite-requesters.component.html
│   │   │   │   │   ├── invite-requesters.component.scss
│   │   │   │   │   ├── invite-requesters.component.spec.ts
│   │   │   │   │   └── invite-requesters.component.ts
│   │   │   │   ├── requester
│   │   │   │   │   ├── requester.component.html
│   │   │   │   │   ├── requester.component.scss
│   │   │   │   │   ├── requester.component.spec.ts
│   │   │   │   │   └── requester.component.ts
│   │   │   │   ├── requester-grid
│   │   │   │   │   ├── requester-grid.component.html
│   │   │   │   │   ├── requester-grid.component.scss
│   │   │   │   │   ├── requester-grid.component.spec.ts
│   │   │   │   │   └── requester-grid.component.ts
│   │   │   │   └── requesters-card
│   │   │   │       ├── requesters-card.component.html
│   │   │   │       ├── requesters-card.component.scss
│   │   │   │       ├── requesters-card.component.spec.ts
│   │   │   │       └── requesters-card.component.ts
│   │   │   ├── requester-routing.module.ts
│   │   │   ├── requester.module.ts
│   │   │   └── services
│   │   │       ├── requester.service.spec.ts
│   │   │       └── requester.service.ts
│   │   ├── response-email-template
│   │   │   ├── components
│   │   │   │   ├── quick-response-template
│   │   │   │   │   ├── quick-response-template.component.html
│   │   │   │   │   ├── quick-response-template.component.scss
│   │   │   │   │   ├── quick-response-template.component.spec.ts
│   │   │   │   │   └── quick-response-template.component.ts
│   │   │   │   └── response-email-template-grid
│   │   │   │       ├── response-email-template-grid.component.html
│   │   │   │       ├── response-email-template-grid.component.scss
│   │   │   │       ├── response-email-template-grid.component.spec.ts
│   │   │   │       └── response-email-template-grid.component.ts
│   │   │   ├── response-email-template-routing.module.ts
│   │   │   └── response-email-template.module.ts
│   │   ├── roles
│   │   │   ├── components
│   │   │   │   ├── role
│   │   │   │   │   ├── role.component.html
│   │   │   │   │   ├── role.component.scss
│   │   │   │   │   ├── role.component.spec.ts
│   │   │   │   │   └── role.component.ts
│   │   │   │   ├── role-card
│   │   │   │   │   ├── role-card.component.html
│   │   │   │   │   ├── role-card.component.scss
│   │   │   │   │   ├── role-card.component.spec.ts
│   │   │   │   │   └── role-card.component.ts
│   │   │   │   ├── role-sekeleton
│   │   │   │   │   ├── role-sekeleton.component.html
│   │   │   │   │   ├── role-sekeleton.component.scss
│   │   │   │   │   ├── role-sekeleton.component.spec.ts
│   │   │   │   │   └── role-sekeleton.component.ts
│   │   │   │   └── user-grid
│   │   │   │       ├── user-grid.component.html
│   │   │   │       ├── user-grid.component.scss
│   │   │   │       ├── user-grid.component.spec.ts
│   │   │   │       └── user-grid.component.ts
│   │   │   ├── roles-routing.module.ts
│   │   │   ├── roles.module.ts
│   │   │   └── services
│   │   │       ├── roles.service.spec.ts
│   │   │       └── roles.service.ts
│   │   ├── select-picker-feature
│   │   │   ├── components
│   │   │   │   ├── select-picker-feature.component.html
│   │   │   │   ├── select-picker-feature.component.scss
│   │   │   │   ├── select-picker-feature.component.spec.ts
│   │   │   │   └── select-picker-feature.component.ts
│   │   │   ├── select-picker-feature-routing.module.ts
│   │   │   ├── select-picker-feature.module.ts
│   │   │   └── services
│   │   │       ├── select-picker-feature.service.spec.ts
│   │   │       └── select-picker-feature.service.ts
│   │   ├── service-catalogue
│   │   │   ├── components
│   │   │   │   ├── add-attachment
│   │   │   │   │   ├── add-attachment.component.html
│   │   │   │   │   ├── add-attachment.component.scss
│   │   │   │   │   ├── add-attachment.component.spec.ts
│   │   │   │   │   └── add-attachment.component.ts
│   │   │   │   ├── add-catalogue
│   │   │   │   │   ├── add-catalogue.component.html
│   │   │   │   │   ├── add-catalogue.component.scss
│   │   │   │   │   ├── add-catalogue.component.spec.ts
│   │   │   │   │   └── add-catalogue.component.ts
│   │   │   │   ├── add-classification
│   │   │   │   │   ├── add-classification.component.html
│   │   │   │   │   ├── add-classification.component.scss
│   │   │   │   │   ├── add-classification.component.spec.ts
│   │   │   │   │   └── add-classification.component.ts
│   │   │   │   ├── add-service
│   │   │   │   │   ├── add-service.component.html
│   │   │   │   │   ├── add-service.component.scss
│   │   │   │   │   ├── add-service.component.spec.ts
│   │   │   │   │   └── add-service.component.ts
│   │   │   │   ├── attach-kb
│   │   │   │   │   ├── attach-kb.component.html
│   │   │   │   │   ├── attach-kb.component.scss
│   │   │   │   │   ├── attach-kb.component.spec.ts
│   │   │   │   │   └── attach-kb.component.ts
│   │   │   │   ├── edit-service
│   │   │   │   │   ├── edit-service.component.html
│   │   │   │   │   ├── edit-service.component.scss
│   │   │   │   │   ├── edit-service.component.spec.ts
│   │   │   │   │   └── edit-service.component.ts
│   │   │   │   ├── preview
│   │   │   │   │   ├── preview.component.html
│   │   │   │   │   ├── preview.component.scss
│   │   │   │   │   ├── preview.component.spec.ts
│   │   │   │   │   └── preview.component.ts
│   │   │   │   ├── select-requester
│   │   │   │   │   ├── select-requester.component.html
│   │   │   │   │   ├── select-requester.component.scss
│   │   │   │   │   ├── select-requester.component.spec.ts
│   │   │   │   │   └── select-requester.component.ts
│   │   │   │   ├── service-details
│   │   │   │   │   ├── service-details.component.html
│   │   │   │   │   ├── service-details.component.scss
│   │   │   │   │   ├── service-details.component.spec.ts
│   │   │   │   │   └── service-details.component.ts
│   │   │   │   ├── service-form
│   │   │   │   │   ├── service-form.component.html
│   │   │   │   │   ├── service-form.component.scss
│   │   │   │   │   ├── service-form.component.spec.ts
│   │   │   │   │   └── service-form.component.ts
│   │   │   │   ├── service-history
│   │   │   │   │   ├── service-history.component.html
│   │   │   │   │   ├── service-history.component.scss
│   │   │   │   │   ├── service-history.component.spec.ts
│   │   │   │   │   └── service-history.component.ts
│   │   │   │   ├── service-list-item
│   │   │   │   │   ├── service-list-item.component.html
│   │   │   │   │   ├── service-list-item.component.scss
│   │   │   │   │   ├── service-list-item.component.spec.ts
│   │   │   │   │   └── service-list-item.component.ts
│   │   │   │   ├── technical-catalogue
│   │   │   │   │   ├── technical-catalogue.component.html
│   │   │   │   │   ├── technical-catalogue.component.scss
│   │   │   │   │   ├── technical-catalogue.component.spec.ts
│   │   │   │   │   └── technical-catalogue.component.ts
│   │   │   │   ├── technical-catalogue-list
│   │   │   │   │   ├── technical-catalogue-list.component.html
│   │   │   │   │   ├── technical-catalogue-list.component.scss
│   │   │   │   │   ├── technical-catalogue-list.component.spec.ts
│   │   │   │   │   └── technical-catalogue-list.component.ts
│   │   │   │   ├── technical-catalogue-sidebar
│   │   │   │   │   ├── technical-catalogue-sidebar.component.html
│   │   │   │   │   ├── technical-catalogue-sidebar.component.scss
│   │   │   │   │   ├── technical-catalogue-sidebar.component.spec.ts
│   │   │   │   │   └── technical-catalogue-sidebar.component.ts
│   │   │   │   └── technical-sekeleton
│   │   │   │       ├── technical-sekeleton.component.html
│   │   │   │       ├── technical-sekeleton.component.scss
│   │   │   │       ├── technical-sekeleton.component.spec.ts
│   │   │   │       └── technical-sekeleton.component.ts
│   │   │   ├── service-catalogue-routing.module.ts
│   │   │   ├── service-catalogue.module.ts
│   │   │   └── services
│   │   │       ├── service-catalogue.service.spec.ts
│   │   │       └── service-catalogue.service.ts
│   │   ├── services
│   │   │   ├── components
│   │   │   │   ├── add-bandwidth-profile
│   │   │   │   │   ├── add-bandwidth-profile.component.html
│   │   │   │   │   ├── add-bandwidth-profile.component.scss
│   │   │   │   │   ├── add-bandwidth-profile.component.spec.ts
│   │   │   │   │   └── add-bandwidth-profile.component.ts
│   │   │   │   ├── add-gpon-services
│   │   │   │   │   ├── add-gpon-services.component.html
│   │   │   │   │   ├── add-gpon-services.component.scss
│   │   │   │   │   ├── add-gpon-services.component.spec.ts
│   │   │   │   │   └── add-gpon-services.component.ts
│   │   │   │   ├── add-service-categories
│   │   │   │   │   ├── add-service-categories.component.html
│   │   │   │   │   ├── add-service-categories.component.scss
│   │   │   │   │   ├── add-service-categories.component.spec.ts
│   │   │   │   │   └── add-service-categories.component.ts
│   │   │   │   ├── add-sni-configuration
│   │   │   │   │   ├── add-sni-configuration.component.html
│   │   │   │   │   ├── add-sni-configuration.component.scss
│   │   │   │   │   ├── add-sni-configuration.component.spec.ts
│   │   │   │   │   └── add-sni-configuration.component.ts
│   │   │   │   ├── circuit-grid
│   │   │   │   │   ├── circuit-grid.component.html
│   │   │   │   │   ├── circuit-grid.component.scss
│   │   │   │   │   ├── circuit-grid.component.spec.ts
│   │   │   │   │   └── circuit-grid.component.ts
│   │   │   │   ├── circuit-paths
│   │   │   │   │   ├── circuit-paths.component.html
│   │   │   │   │   ├── circuit-paths.component.scss
│   │   │   │   │   ├── circuit-paths.component.spec.ts
│   │   │   │   │   └── circuit-paths.component.ts
│   │   │   │   ├── delete-service
│   │   │   │   │   ├── delete-service.component.html
│   │   │   │   │   ├── delete-service.component.scss
│   │   │   │   │   ├── delete-service.component.spec.ts
│   │   │   │   │   └── delete-service.component.ts
│   │   │   │   ├── eth-services
│   │   │   │   │   ├── eth-services.component.html
│   │   │   │   │   ├── eth-services.component.scss
│   │   │   │   │   ├── eth-services.component.spec.ts
│   │   │   │   │   └── eth-services.component.ts
│   │   │   │   ├── eth-terminated-services
│   │   │   │   │   ├── eth-terminated-services.component.html
│   │   │   │   │   ├── eth-terminated-services.component.scss
│   │   │   │   │   ├── eth-terminated-services.component.spec.ts
│   │   │   │   │   └── eth-terminated-services.component.ts
│   │   │   │   ├── ethernet-services
│   │   │   │   │   ├── ethernet-services.component.html
│   │   │   │   │   ├── ethernet-services.component.scss
│   │   │   │   │   ├── ethernet-services.component.spec.ts
│   │   │   │   │   └── ethernet-services.component.ts
│   │   │   │   ├── ethernet-services-paths
│   │   │   │   │   ├── ethernet-services-paths.component.html
│   │   │   │   │   ├── ethernet-services-paths.component.scss
│   │   │   │   │   ├── ethernet-services-paths.component.spec.ts
│   │   │   │   │   └── ethernet-services-paths.component.ts
│   │   │   │   ├── gpon-bandwidth-profile
│   │   │   │   │   ├── gpon-bandwidth-profile.component.html
│   │   │   │   │   ├── gpon-bandwidth-profile.component.scss
│   │   │   │   │   ├── gpon-bandwidth-profile.component.spec.ts
│   │   │   │   │   └── gpon-bandwidth-profile.component.ts
│   │   │   │   ├── gpon-services
│   │   │   │   │   ├── gpon-services.component.html
│   │   │   │   │   ├── gpon-services.component.scss
│   │   │   │   │   ├── gpon-services.component.spec.ts
│   │   │   │   │   └── gpon-services.component.ts
│   │   │   │   ├── gpon-sni-configuration
│   │   │   │   │   ├── gpon-sni-configuration.component.html
│   │   │   │   │   ├── gpon-sni-configuration.component.scss
│   │   │   │   │   ├── gpon-sni-configuration.component.spec.ts
│   │   │   │   │   └── gpon-sni-configuration.component.ts
│   │   │   │   ├── gpon-unknown-services
│   │   │   │   │   ├── gpon-unknown-services.component.html
│   │   │   │   │   ├── gpon-unknown-services.component.scss
│   │   │   │   │   ├── gpon-unknown-services.component.spec.ts
│   │   │   │   │   └── gpon-unknown-services.component.ts
│   │   │   │   ├── pdh-services
│   │   │   │   │   ├── pdh-services.component.html
│   │   │   │   │   ├── pdh-services.component.scss
│   │   │   │   │   ├── pdh-services.component.spec.ts
│   │   │   │   │   └── pdh-services.component.ts
│   │   │   │   ├── pdh-terminated-services
│   │   │   │   │   ├── pdh-terminated-services.component.html
│   │   │   │   │   ├── pdh-terminated-services.component.scss
│   │   │   │   │   ├── pdh-terminated-services.component.spec.ts
│   │   │   │   │   └── pdh-terminated-services.component.ts
│   │   │   │   ├── sdh-services
│   │   │   │   │   ├── sdh-services.component.html
│   │   │   │   │   ├── sdh-services.component.scss
│   │   │   │   │   ├── sdh-services.component.spec.ts
│   │   │   │   │   └── sdh-services.component.ts
│   │   │   │   ├── service-activation
│   │   │   │   │   ├── service-activation.component.html
│   │   │   │   │   ├── service-activation.component.scss
│   │   │   │   │   ├── service-activation.component.spec.ts
│   │   │   │   │   └── service-activation.component.ts
│   │   │   │   ├── service-card
│   │   │   │   │   ├── service-card.component.html
│   │   │   │   │   ├── service-card.component.scss
│   │   │   │   │   ├── service-card.component.spec.ts
│   │   │   │   │   └── service-card.component.ts
│   │   │   │   ├── service-grid
│   │   │   │   │   ├── service-grid.component.html
│   │   │   │   │   ├── service-grid.component.scss
│   │   │   │   │   ├── service-grid.component.spec.ts
│   │   │   │   │   └── service-grid.component.ts
│   │   │   │   ├── service-pm-data
│   │   │   │   │   ├── service-pm-data.component.html
│   │   │   │   │   ├── service-pm-data.component.scss
│   │   │   │   │   ├── service-pm-data.component.spec.ts
│   │   │   │   │   └── service-pm-data.component.ts
│   │   │   │   ├── services-info
│   │   │   │   │   ├── services-info.component.html
│   │   │   │   │   ├── services-info.component.scss
│   │   │   │   │   ├── services-info.component.spec.ts
│   │   │   │   │   └── services-info.component.ts
│   │   │   │   ├── stm-trails-grid
│   │   │   │   │   ├── stm-trails-grid.component.html
│   │   │   │   │   ├── stm-trails-grid.component.scss
│   │   │   │   │   ├── stm-trails-grid.component.spec.ts
│   │   │   │   │   └── stm-trails-grid.component.ts
│   │   │   │   ├── stm-trails-paths
│   │   │   │   │   ├── stm-trails-paths.component.html
│   │   │   │   │   ├── stm-trails-paths.component.scss
│   │   │   │   │   ├── stm-trails-paths.component.spec.ts
│   │   │   │   │   └── stm-trails-paths.component.ts
│   │   │   │   ├── terminated-service
│   │   │   │   │   ├── terminated-service.component.html
│   │   │   │   │   ├── terminated-service.component.scss
│   │   │   │   │   ├── terminated-service.component.spec.ts
│   │   │   │   │   └── terminated-service.component.ts
│   │   │   │   ├── trace-test-sidebar
│   │   │   │   │   ├── trace-test-sidebar.component.html
│   │   │   │   │   ├── trace-test-sidebar.component.scss
│   │   │   │   │   ├── trace-test-sidebar.component.spec.ts
│   │   │   │   │   └── trace-test-sidebar.component.ts
│   │   │   │   ├── tunnels-services
│   │   │   │   │   ├── tunnels-services.component.html
│   │   │   │   │   ├── tunnels-services.component.scss
│   │   │   │   │   ├── tunnels-services.component.spec.ts
│   │   │   │   │   └── tunnels-services.component.ts
│   │   │   │   ├── unknown-service-info-sidebar
│   │   │   │   │   ├── unknown-service-info-sidebar.component.html
│   │   │   │   │   ├── unknown-service-info-sidebar.component.scss
│   │   │   │   │   ├── unknown-service-info-sidebar.component.spec.ts
│   │   │   │   │   └── unknown-service-info-sidebar.component.ts
│   │   │   │   ├── unknown-service-reconcile
│   │   │   │   │   ├── unknown-service-reconcile.component.html
│   │   │   │   │   ├── unknown-service-reconcile.component.scss
│   │   │   │   │   ├── unknown-service-reconcile.component.spec.ts
│   │   │   │   │   └── unknown-service-reconcile.component.ts
│   │   │   │   ├── vcg-trails-grid
│   │   │   │   │   ├── vcg-trails-grid.component.html
│   │   │   │   │   ├── vcg-trails-grid.component.scss
│   │   │   │   │   ├── vcg-trails-grid.component.spec.ts
│   │   │   │   │   └── vcg-trails-grid.component.ts
│   │   │   │   └── vcg-trails-paths
│   │   │   │       ├── vcg-trails-paths.component.html
│   │   │   │       ├── vcg-trails-paths.component.scss
│   │   │   │       ├── vcg-trails-paths.component.spec.ts
│   │   │   │       └── vcg-trails-paths.component.ts
│   │   │   ├── service-routing.module.ts
│   │   │   ├── service.module.ts
│   │   │   ├── service.service.spec.ts
│   │   │   └── service.service.ts
│   │   ├── setting
│   │   │   ├── components
│   │   │   │   ├── prefix-configuration
│   │   │   │   │   ├── prefix-configuration.component.html
│   │   │   │   │   ├── prefix-configuration.component.scss
│   │   │   │   │   ├── prefix-configuration.component.spec.ts
│   │   │   │   │   └── prefix-configuration.component.ts
│   │   │   │   └── setting
│   │   │   │       ├── setting.component.html
│   │   │   │       ├── setting.component.scss
│   │   │   │       ├── setting.component.spec.ts
│   │   │   │       └── setting.component.ts
│   │   │   ├── services
│   │   │   │   ├── setting.service.spec.ts
│   │   │   │   └── setting.service.ts
│   │   │   ├── setting-routing.module.ts
│   │   │   └── setting.module.ts
│   │   ├── shift-management
│   │   │   ├── components
│   │   │   │   ├── add-shift
│   │   │   │   │   ├── add-shift.component.html
│   │   │   │   │   ├── add-shift.component.scss
│   │   │   │   │   ├── add-shift.component.spec.ts
│   │   │   │   │   └── add-shift.component.ts
│   │   │   │   ├── shift-management-grid
│   │   │   │   │   ├── shift-management-grid.component.html
│   │   │   │   │   ├── shift-management-grid.component.scss
│   │   │   │   │   ├── shift-management-grid.component.spec.ts
│   │   │   │   │   └── shift-management-grid.component.ts
│   │   │   │   ├── view-shift
│   │   │   │   │   ├── view-shift.component.html
│   │   │   │   │   ├── view-shift.component.scss
│   │   │   │   │   ├── view-shift.component.spec.ts
│   │   │   │   │   └── view-shift.component.ts
│   │   │   │   └── vis-timeline-calendar
│   │   │   │       ├── vis-timeline-calendar.component.html
│   │   │   │       ├── vis-timeline-calendar.component.scss
│   │   │   │       ├── vis-timeline-calendar.component.spec.ts
│   │   │   │       └── vis-timeline-calendar.component.ts
│   │   │   ├── models
│   │   │   │   └── shift.ts
│   │   │   ├── services
│   │   │   │   ├── shift.service.spec.ts
│   │   │   │   └── shift.service.ts
│   │   │   ├── shift-management-routing.module.ts
│   │   │   └── shift-management.module.ts
│   │   ├── sla
│   │   │   ├── components
│   │   │   │   ├── adjustment
│   │   │   │   │   ├── adjustment.component.html
│   │   │   │   │   ├── adjustment.component.scss
│   │   │   │   │   ├── adjustment.component.spec.ts
│   │   │   │   │   └── adjustment.component.ts
│   │   │   │   ├── escalation
│   │   │   │   │   ├── escalation.component.html
│   │   │   │   │   ├── escalation.component.scss
│   │   │   │   │   ├── escalation.component.spec.ts
│   │   │   │   │   └── escalation.component.ts
│   │   │   │   ├── ola-and-uc
│   │   │   │   │   ├── ola-and-uc.component.html
│   │   │   │   │   ├── ola-and-uc.component.scss
│   │   │   │   │   ├── ola-and-uc.component.spec.ts
│   │   │   │   │   └── ola-and-uc.component.ts
│   │   │   │   ├── pso
│   │   │   │   │   ├── pso.component.html
│   │   │   │   │   ├── pso.component.scss
│   │   │   │   │   ├── pso.component.spec.ts
│   │   │   │   │   └── pso.component.ts
│   │   │   │   ├── related-request
│   │   │   │   │   ├── related-request.component.html
│   │   │   │   │   ├── related-request.component.scss
│   │   │   │   │   ├── related-request.component.spec.ts
│   │   │   │   │   └── related-request.component.ts
│   │   │   │   ├── sla
│   │   │   │   │   ├── sla.component.html
│   │   │   │   │   ├── sla.component.scss
│   │   │   │   │   ├── sla.component.spec.ts
│   │   │   │   │   └── sla.component.ts
│   │   │   │   ├── sla-edit
│   │   │   │   │   ├── sla-edit.component.html
│   │   │   │   │   ├── sla-edit.component.scss
│   │   │   │   │   ├── sla-edit.component.spec.ts
│   │   │   │   │   └── sla-edit.component.ts
│   │   │   │   ├── sla-grid
│   │   │   │   │   ├── sla-grid.component.html
│   │   │   │   │   ├── sla-grid.component.scss
│   │   │   │   │   ├── sla-grid.component.spec.ts
│   │   │   │   │   └── sla-grid.component.ts
│   │   │   │   └── sla-history
│   │   │   │       ├── sla-history.component.html
│   │   │   │       ├── sla-history.component.scss
│   │   │   │       ├── sla-history.component.spec.ts
│   │   │   │       └── sla-history.component.ts
│   │   │   ├── services
│   │   │   │   ├── sla.service.spec.ts
│   │   │   │   └── sla.service.ts
│   │   │   ├── sla-routing.module.ts
│   │   │   └── sla.module.ts
│   │   ├── sms-config
│   │   │   ├── components
│   │   │   │   ├── msp-sms-config-grid
│   │   │   │   │   ├── msp-sms-config-grid.component.html
│   │   │   │   │   ├── msp-sms-config-grid.component.scss
│   │   │   │   │   ├── msp-sms-config-grid.component.spec.ts
│   │   │   │   │   └── msp-sms-config-grid.component.ts
│   │   │   │   ├── sms-config
│   │   │   │   │   ├── sms-config.component.html
│   │   │   │   │   ├── sms-config.component.scss
│   │   │   │   │   ├── sms-config.component.spec.ts
│   │   │   │   │   └── sms-config.component.ts
│   │   │   │   └── sms-config-sidebar
│   │   │   │       ├── sms-config-sidebar.component.html
│   │   │   │       ├── sms-config-sidebar.component.scss
│   │   │   │       ├── sms-config-sidebar.component.spec.ts
│   │   │   │       └── sms-config-sidebar.component.ts
│   │   │   ├── services
│   │   │   │   ├── sms.service.spec.ts
│   │   │   │   └── sms.service.ts
│   │   │   ├── sms-config-routing.module.ts
│   │   │   └── sms-config.module.ts
│   │   ├── sso
│   │   │   ├── component
│   │   │   │   ├── risl-sso-auth
│   │   │   │   │   ├── risl-sso-auth.component.html
│   │   │   │   │   ├── risl-sso-auth.component.scss
│   │   │   │   │   ├── risl-sso-auth.component.spec.ts
│   │   │   │   │   └── risl-sso-auth.component.ts
│   │   │   │   └── sso
│   │   │   │       ├── sso.component.html
│   │   │   │       ├── sso.component.scss
│   │   │   │       ├── sso.component.spec.ts
│   │   │   │       └── sso.component.ts
│   │   │   ├── services
│   │   │   │   ├── sso.service.spec.ts
│   │   │   │   └── sso.service.ts
│   │   │   ├── sso-routing.module.ts
│   │   │   └── sso.module.ts
│   │   ├── ssologout
│   │   │   ├── component
│   │   │   │   ├── risl-sso-logout
│   │   │   │   │   ├── risl-sso-logout.component.html
│   │   │   │   │   ├── risl-sso-logout.component.scss
│   │   │   │   │   ├── risl-sso-logout.component.spec.ts
│   │   │   │   │   └── risl-sso-logout.component.ts
│   │   │   │   └── ssologout
│   │   │   │       ├── ssologout.component.html
│   │   │   │       ├── ssologout.component.scss
│   │   │   │       ├── ssologout.component.spec.ts
│   │   │   │       └── ssologout.component.ts
│   │   │   ├── services
│   │   │   │   ├── ssologout.service.spec.ts
│   │   │   │   └── ssologout.service.ts
│   │   │   ├── ssologout-routing.module.ts
│   │   │   └── ssologout.module.ts
│   │   ├── support-email
│   │   │   ├── components
│   │   │   │   ├── config-smtp
│   │   │   │   │   ├── config-smtp.component.html
│   │   │   │   │   ├── config-smtp.component.scss
│   │   │   │   │   ├── config-smtp.component.spec.ts
│   │   │   │   │   └── config-smtp.component.ts
│   │   │   │   ├── msp-smtp-config-grid
│   │   │   │   │   ├── msp-smtp-config-grid.component.html
│   │   │   │   │   ├── msp-smtp-config-grid.component.scss
│   │   │   │   │   ├── msp-smtp-config-grid.component.spec.ts
│   │   │   │   │   └── msp-smtp-config-grid.component.ts
│   │   │   │   ├── smtp-profile
│   │   │   │   │   ├── smtp-profile.component.html
│   │   │   │   │   ├── smtp-profile.component.scss
│   │   │   │   │   ├── smtp-profile.component.spec.ts
│   │   │   │   │   └── smtp-profile.component.ts
│   │   │   │   └── support-email
│   │   │   │       ├── support-email.component.html
│   │   │   │       ├── support-email.component.scss
│   │   │   │       ├── support-email.component.spec.ts
│   │   │   │       └── support-email.component.ts
│   │   │   ├── services
│   │   │   │   ├── support-email.service.spec.ts
│   │   │   │   └── support-email.service.ts
│   │   │   ├── support-email-routing.module.ts
│   │   │   └── support-email.module.ts
│   │   ├── system-menu
│   │   │   ├── components
│   │   │   │   ├── account-setting-skeleton
│   │   │   │   │   ├── account-setting-skeleton.component.html
│   │   │   │   │   ├── account-setting-skeleton.component.scss
│   │   │   │   │   ├── account-setting-skeleton.component.spec.ts
│   │   │   │   │   └── account-setting-skeleton.component.ts
│   │   │   │   ├── account-settings
│   │   │   │   │   ├── account-settings.component.html
│   │   │   │   │   ├── account-settings.component.scss
│   │   │   │   │   ├── account-settings.component.spec.ts
│   │   │   │   │   └── account-settings.component.ts
│   │   │   │   ├── account-sidebar
│   │   │   │   │   ├── account-sidebar.component.html
│   │   │   │   │   ├── account-sidebar.component.scss
│   │   │   │   │   ├── account-sidebar.component.spec.ts
│   │   │   │   │   └── account-sidebar.component.ts
│   │   │   │   ├── add-signature
│   │   │   │   │   ├── add-signature.component.html
│   │   │   │   │   ├── add-signature.component.scss
│   │   │   │   │   ├── add-signature.component.spec.ts
│   │   │   │   │   └── add-signature.component.ts
│   │   │   │   ├── admin-popover
│   │   │   │   │   ├── admin-popover.component.html
│   │   │   │   │   ├── admin-popover.component.scss
│   │   │   │   │   ├── admin-popover.component.spec.ts
│   │   │   │   │   └── admin-popover.component.ts
│   │   │   │   ├── keyboard-shortcut
│   │   │   │   │   ├── keyboard-shortcut.component.html
│   │   │   │   │   ├── keyboard-shortcut.component.scss
│   │   │   │   │   ├── keyboard-shortcut.component.spec.ts
│   │   │   │   │   └── keyboard-shortcut.component.ts
│   │   │   │   └── search-menu
│   │   │   │       ├── search-menu.component.html
│   │   │   │       ├── search-menu.component.scss
│   │   │   │       ├── search-menu.component.spec.ts
│   │   │   │       ├── search-menu.component.ts
│   │   │   │       └── search-menu.component1.html
│   │   │   ├── services
│   │   │   │   ├── system-menu.service.spec.ts
│   │   │   │   └── system-menu.service.ts
│   │   │   ├── system-menu-routing.module.ts
│   │   │   └── system-menu.module.ts
│   │   ├── tags
│   │   │   ├── components
│   │   │   │   ├── tag
│   │   │   │   │   ├── tag.component.html
│   │   │   │   │   ├── tag.component.scss
│   │   │   │   │   ├── tag.component.spec.ts
│   │   │   │   │   └── tag.component.ts
│   │   │   │   ├── tag-card
│   │   │   │   │   ├── tag-card.component.html
│   │   │   │   │   ├── tag-card.component.scss
│   │   │   │   │   ├── tag-card.component.spec.ts
│   │   │   │   │   └── tag-card.component.ts
│   │   │   │   └── tag-grid
│   │   │   │       ├── tag-grid.component.html
│   │   │   │       ├── tag-grid.component.scss
│   │   │   │       ├── tag-grid.component.spec.ts
│   │   │   │       └── tag-grid.component.ts
│   │   │   ├── services
│   │   │   │   ├── tag.service.spec.ts
│   │   │   │   └── tag.service.ts
│   │   │   ├── tags-routing.module.ts
│   │   │   └── tags.module.ts
│   │   ├── teams
│   │   │   ├── components
│   │   │   │   ├── team-skeleton
│   │   │   │   │   ├── team-skeleton.component.html
│   │   │   │   │   ├── team-skeleton.component.scss
│   │   │   │   │   ├── team-skeleton.component.spec.ts
│   │   │   │   │   └── team-skeleton.component.ts
│   │   │   │   ├── teams
│   │   │   │   │   ├── teams.component.html
│   │   │   │   │   ├── teams.component.scss
│   │   │   │   │   ├── teams.component.spec.ts
│   │   │   │   │   └── teams.component.ts
│   │   │   │   ├── teams-card
│   │   │   │   │   ├── teams-card.component.html
│   │   │   │   │   ├── teams-card.component.scss
│   │   │   │   │   ├── teams-card.component.spec.ts
│   │   │   │   │   └── teams-card.component.ts
│   │   │   │   ├── teams-grid
│   │   │   │   │   ├── teams-grid.component.html
│   │   │   │   │   ├── teams-grid.component.scss
│   │   │   │   │   ├── teams-grid.component.spec.ts
│   │   │   │   │   └── teams-grid.component.ts
│   │   │   │   ├── teams-level
│   │   │   │   │   ├── teams-level.component.html
│   │   │   │   │   ├── teams-level.component.scss
│   │   │   │   │   ├── teams-level.component.spec.ts
│   │   │   │   │   └── teams-level.component.ts
│   │   │   │   ├── teams-profile
│   │   │   │   │   ├── teams-profile.component.html
│   │   │   │   │   ├── teams-profile.component.scss
│   │   │   │   │   ├── teams-profile.component.spec.ts
│   │   │   │   │   └── teams-profile.component.ts
│   │   │   │   ├── teams-sub-group
│   │   │   │   │   ├── teams-sub-group.component.html
│   │   │   │   │   ├── teams-sub-group.component.scss
│   │   │   │   │   ├── teams-sub-group.component.spec.ts
│   │   │   │   │   └── teams-sub-group.component.ts
│   │   │   │   └── update-escalation
│   │   │   │       ├── update-escalation.component.html
│   │   │   │       ├── update-escalation.component.scss
│   │   │   │       ├── update-escalation.component.spec.ts
│   │   │   │       └── update-escalation.component.ts
│   │   │   ├── services
│   │   │   │   ├── teams.service.spec.ts
│   │   │   │   └── teams.service.ts
│   │   │   ├── teams-routing.module.ts
│   │   │   └── teams.module.ts
│   │   ├── template
│   │   │   ├── component
│   │   │   │   ├── create-new-template
│   │   │   │   │   ├── create-new-template.component.html
│   │   │   │   │   ├── create-new-template.component.scss
│   │   │   │   │   ├── create-new-template.component.spec.ts
│   │   │   │   │   └── create-new-template.component.ts
│   │   │   │   ├── template-category
│   │   │   │   │   ├── template-category.component.html
│   │   │   │   │   ├── template-category.component.scss
│   │   │   │   │   ├── template-category.component.spec.ts
│   │   │   │   │   └── template-category.component.ts
│   │   │   │   ├── template-category-sidebar
│   │   │   │   │   ├── template-category-sidebar.component.html
│   │   │   │   │   ├── template-category-sidebar.component.scss
│   │   │   │   │   ├── template-category-sidebar.component.spec.ts
│   │   │   │   │   └── template-category-sidebar.component.ts
│   │   │   │   ├── template-data-badge
│   │   │   │   │   ├── template-data-badge.component.html
│   │   │   │   │   ├── template-data-badge.component.scss
│   │   │   │   │   ├── template-data-badge.component.spec.ts
│   │   │   │   │   └── template-data-badge.component.ts
│   │   │   │   └── template-grid
│   │   │   │       ├── template-grid.component.html
│   │   │   │       ├── template-grid.component.scss
│   │   │   │       ├── template-grid.component.spec.ts
│   │   │   │       └── template-grid.component.ts
│   │   │   ├── services
│   │   │   │   ├── template.service.spec.ts
│   │   │   │   └── template.service.ts
│   │   │   ├── template-routing.module.ts
│   │   │   └── template.module.ts
│   │   ├── threshold
│   │   │   ├── components
│   │   │   │   ├── threshold
│   │   │   │   │   ├── threshold.component.html
│   │   │   │   │   ├── threshold.component.scss
│   │   │   │   │   ├── threshold.component.spec.ts
│   │   │   │   │   └── threshold.component.ts
│   │   │   │   └── threshold-add
│   │   │   │       ├── threshold-add.component.html
│   │   │   │       ├── threshold-add.component.scss
│   │   │   │       ├── threshold-add.component.spec.ts
│   │   │   │       └── threshold-add.component.ts
│   │   │   ├── services
│   │   │   │   ├── threshold.service.spec.ts
│   │   │   │   └── threshold.service.ts
│   │   │   ├── threshold-routing.module.ts
│   │   │   └── threshold.module.ts
│   │   ├── topology
│   │   │   ├── components
│   │   │   │   ├── all-topology-new-profile
│   │   │   │   │   ├── all-topology-new-profile.component.html
│   │   │   │   │   ├── all-topology-new-profile.component.scss
│   │   │   │   │   ├── all-topology-new-profile.component.spec.ts
│   │   │   │   │   └── all-topology-new-profile.component.ts
│   │   │   │   ├── topology
│   │   │   │   │   ├── topology.component.html
│   │   │   │   │   ├── topology.component.scss
│   │   │   │   │   ├── topology.component.spec.ts
│   │   │   │   │   └── topology.component.ts
│   │   │   │   ├── topology-add
│   │   │   │   │   ├── topology-add.component.html
│   │   │   │   │   ├── topology-add.component.scss
│   │   │   │   │   ├── topology-add.component.spec.ts
│   │   │   │   │   └── topology-add.component.ts
│   │   │   │   ├── topology-links
│   │   │   │   │   ├── topology-link.component.ts
│   │   │   │   │   ├── topology-links.component.html
│   │   │   │   │   ├── topology-links.component.scss
│   │   │   │   │   └── topology-links.component.spec.ts
│   │   │   │   └── topology-view
│   │   │   │       ├── topology-view.component.html
│   │   │   │       ├── topology-view.component.scss
│   │   │   │       ├── topology-view.component.spec.ts
│   │   │   │       └── topology-view.component.ts
│   │   │   ├── services
│   │   │   │   ├── topology.service.spec.ts
│   │   │   │   └── topology.service.ts
│   │   │   ├── topology-routing.module.ts
│   │   │   └── topology.module.ts
│   │   ├── tree-crud-view
│   │   │   ├── components
│   │   │   │   └── tree-crud-view
│   │   │   │       ├── tree-crud-view.component.html
│   │   │   │       ├── tree-crud-view.component.scss
│   │   │   │       ├── tree-crud-view.component.spec.ts
│   │   │   │       └── tree-crud-view.component.ts
│   │   │   ├── services
│   │   │   │   ├── tree-crud-view.service.spec.ts
│   │   │   │   └── tree-crud-view.service.ts
│   │   │   ├── tree-crud-view-routing.module.ts
│   │   │   └── tree-crud-view.module.ts
│   │   ├── trigger-configuration
│   │   │   ├── components
│   │   │   │   ├── trigger
│   │   │   │   │   ├── trigger.component.html
│   │   │   │   │   ├── trigger.component.scss
│   │   │   │   │   ├── trigger.component.spec.ts
│   │   │   │   │   └── trigger.component.ts
│   │   │   │   ├── trigger-grid
│   │   │   │   │   ├── trigger-grid.component.html
│   │   │   │   │   ├── trigger-grid.component.scss
│   │   │   │   │   ├── trigger-grid.component.spec.ts
│   │   │   │   │   └── trigger-grid.component.ts
│   │   │   │   └── trigger-time
│   │   │   │       ├── trigger-time.component.html
│   │   │   │       ├── trigger-time.component.scss
│   │   │   │       ├── trigger-time.component.spec.ts
│   │   │   │       └── trigger-time.component.ts
│   │   │   ├── services
│   │   │   │   ├── trigger-configuration.service.spec.ts
│   │   │   │   └── trigger-configuration.service.ts
│   │   │   ├── trigger-configuration-routing.module.ts
│   │   │   └── trigger-configuration.module.ts
│   │   ├── users
│   │   │   ├── components
│   │   │   │   ├── active-users-grid
│   │   │   │   │   ├── active-users-grid.component.html
│   │   │   │   │   ├── active-users-grid.component.scss
│   │   │   │   │   ├── active-users-grid.component.spec.ts
│   │   │   │   │   └── active-users-grid.component.ts
│   │   │   │   ├── invite-user-grid
│   │   │   │   │   ├── invite-user-grid.component.html
│   │   │   │   │   ├── invite-user-grid.component.scss
│   │   │   │   │   ├── invite-user-grid.component.spec.ts
│   │   │   │   │   └── invite-user-grid.component.ts
│   │   │   │   ├── invite-users
│   │   │   │   │   ├── invite-users.component.html
│   │   │   │   │   ├── invite-users.component.scss
│   │   │   │   │   ├── invite-users.component.spec.ts
│   │   │   │   │   └── invite-users.component.ts
│   │   │   │   ├── user
│   │   │   │   │   ├── user.component.html
│   │   │   │   │   ├── user.component.scss
│   │   │   │   │   ├── user.component.spec.ts
│   │   │   │   │   └── user.component.ts
│   │   │   │   ├── user-import
│   │   │   │   │   ├── user-import.component.html
│   │   │   │   │   ├── user-import.component.scss
│   │   │   │   │   ├── user-import.component.spec.ts
│   │   │   │   │   └── user-import.component.ts
│   │   │   │   ├── user-location
│   │   │   │   │   ├── user-location.component.html
│   │   │   │   │   ├── user-location.component.scss
│   │   │   │   │   ├── user-location.component.spec.ts
│   │   │   │   │   └── user-location.component.ts
│   │   │   │   ├── users-card
│   │   │   │   │   ├── users-card.component.html
│   │   │   │   │   ├── users-card.component.scss
│   │   │   │   │   ├── users-card.component.spec.ts
│   │   │   │   │   └── users-card.component.ts
│   │   │   │   └── users-grid
│   │   │   │       ├── delete-user-replacement.html
│   │   │   │       ├── users-grid.component.html
│   │   │   │       ├── users-grid.component.scss
│   │   │   │       ├── users-grid.component.spec.ts
│   │   │   │       └── users-grid.component.ts
│   │   │   ├── services
│   │   │   │   ├── user.service.spec.ts
│   │   │   │   └── user.service.ts
│   │   │   ├── users-routing.module.ts
│   │   │   └── users.module.ts
│   │   ├── vendor
│   │   │   ├── components
│   │   │   │   ├── vendor
│   │   │   │   │   ├── vendor.component.html
│   │   │   │   │   ├── vendor.component.scss
│   │   │   │   │   ├── vendor.component.spec.ts
│   │   │   │   │   └── vendor.component.ts
│   │   │   │   └── vendor-grid
│   │   │   │       ├── vendor-grid.component.html
│   │   │   │       ├── vendor-grid.component.scss
│   │   │   │       ├── vendor-grid.component.spec.ts
│   │   │   │       └── vendor-grid.component.ts
│   │   │   ├── services
│   │   │   │   ├── vendor.service.spec.ts
│   │   │   │   └── vendor.service.ts
│   │   │   ├── vendor-routing.module.ts
│   │   │   └── vendor.module.ts
│   │   ├── work-space
│   │   │   ├── components
│   │   │   │   ├── convert-incident
│   │   │   │   │   ├── convert-incident.component.html
│   │   │   │   │   ├── convert-incident.component.scss
│   │   │   │   │   ├── convert-incident.component.spec.ts
│   │   │   │   │   └── convert-incident.component.ts
│   │   │   │   ├── default-role
│   │   │   │   │   ├── default-role.component.html
│   │   │   │   │   ├── default-role.component.scss
│   │   │   │   │   ├── default-role.component.spec.ts
│   │   │   │   │   └── default-role.component.ts
│   │   │   │   ├── fileters
│   │   │   │   │   ├── fileters.component.html
│   │   │   │   │   ├── fileters.component.scss
│   │   │   │   │   ├── fileters.component.spec.ts
│   │   │   │   │   └── fileters.component.ts
│   │   │   │   ├── members
│   │   │   │   │   ├── members.component.html
│   │   │   │   │   ├── members.component.scss
│   │   │   │   │   ├── members.component.spec.ts
│   │   │   │   │   └── members.component.ts
│   │   │   │   ├── reply-sidebar
│   │   │   │   │   ├── reply-sidebar.component.html
│   │   │   │   │   ├── reply-sidebar.component.scss
│   │   │   │   │   ├── reply-sidebar.component.spec.ts
│   │   │   │   │   └── reply-sidebar.component.ts
│   │   │   │   ├── role-service
│   │   │   │   │   ├── role-service.component.html
│   │   │   │   │   ├── role-service.component.scss
│   │   │   │   │   ├── role-service.component.spec.ts
│   │   │   │   │   └── role-service.component.ts
│   │   │   │   ├── roles-and-permission
│   │   │   │   │   ├── roles-and-permission.component.html
│   │   │   │   │   ├── roles-and-permission.component.scss
│   │   │   │   │   ├── roles-and-permission.component.spec.ts
│   │   │   │   │   └── roles-and-permission.component.ts
│   │   │   │   ├── testing-team-sidebar
│   │   │   │   │   ├── testing-team-sidebar.component.html
│   │   │   │   │   ├── testing-team-sidebar.component.scss
│   │   │   │   │   ├── testing-team-sidebar.component.spec.ts
│   │   │   │   │   └── testing-team-sidebar.component.ts
│   │   │   │   ├── testing-team-sidebar-services
│   │   │   │   │   ├── testing-team-sidebar-services.component.html
│   │   │   │   │   ├── testing-team-sidebar-services.component.scss
│   │   │   │   │   ├── testing-team-sidebar-services.component.spec.ts
│   │   │   │   │   └── testing-team-sidebar-services.component.ts
│   │   │   │   └── work-space
│   │   │   │       ├── work-space.component.html
│   │   │   │       ├── work-space.component.scss
│   │   │   │       ├── work-space.component.spec.ts
│   │   │   │       ├── work-space.component.ts
│   │   │   │       └── workspace_json.json
│   │   │   ├── services
│   │   │   │   ├── work-space.service.spec.ts
│   │   │   │   └── work-space.service.ts
│   │   │   ├── work-space-routing.module.ts
│   │   │   └── work-space.module.ts
│   │   └── workflow
│   │       ├── components
│   │       │   ├── field-constraints
│   │       │   │   ├── field-constraints.component.html
│   │       │   │   ├── field-constraints.component.scss
│   │       │   │   ├── field-constraints.component.spec.ts
│   │       │   │   └── field-constraints.component.ts
│   │       │   ├── permissions
│   │       │   │   ├── permissions.component.html
│   │       │   │   ├── permissions.component.scss
│   │       │   │   ├── permissions.component.spec.ts
│   │       │   │   └── permissions.component.ts
│   │       │   ├── state-automations
│   │       │   │   ├── state-automations.component.html
│   │       │   │   ├── state-automations.component.scss
│   │       │   │   ├── state-automations.component.spec.ts
│   │       │   │   └── state-automations.component.ts
│   │       │   ├── workflow
│   │       │   │   ├── workflow.component.html
│   │       │   │   ├── workflow.component.scss
│   │       │   │   ├── workflow.component.spec.ts
│   │       │   │   └── workflow.component.ts
│   │       │   ├── workflow-add
│   │       │   │   ├── workflow-add.component.html
│   │       │   │   ├── workflow-add.component.scss
│   │       │   │   ├── workflow-add.component.spec.ts
│   │       │   │   └── workflow-add.component.ts
│   │       │   ├── workflow-card
│   │       │   │   ├── workflow-card.component.html
│   │       │   │   ├── workflow-card.component.scss
│   │       │   │   ├── workflow-card.component.spec.ts
│   │       │   │   └── workflow-card.component.ts
│   │       │   └── workflow-grid
│   │       │       ├── workflow-grid.component.html
│   │       │       ├── workflow-grid.component.scss
│   │       │       ├── workflow-grid.component.spec.ts
│   │       │       └── workflow-grid.component.ts
│   │       ├── services
│   │       │   ├── workflow.data.service.ts
│   │       │   ├── workflow.service.spec.ts
│   │       │   └── workflow.service.ts
│   │       ├── workflow-routing.module.ts
│   │       └── workflow.module.ts
│   ├── colors.const.ts
│   ├── common
│   │   ├── dns
│   │   │   ├── animations
│   │   │   │   └── animations.ts
│   │   │   ├── components
│   │   │   │   ├── add-escalation
│   │   │   │   │   ├── add-escalation.component.html
│   │   │   │   │   ├── add-escalation.component.scss
│   │   │   │   │   ├── add-escalation.component.spec.ts
│   │   │   │   │   └── add-escalation.component.ts
│   │   │   │   ├── add-response-email-template
│   │   │   │   │   ├── add-response-email-template.component.html
│   │   │   │   │   ├── add-response-email-template.component.scss
│   │   │   │   │   ├── add-response-email-template.component.spec.ts
│   │   │   │   │   └── add-response-email-template.component.ts
│   │   │   │   ├── ai-based-kb
│   │   │   │   │   ├── ai-based-kb.component.html
│   │   │   │   │   ├── ai-based-kb.component.scss
│   │   │   │   │   ├── ai-based-kb.component.spec.ts
│   │   │   │   │   └── ai-based-kb.component.ts
│   │   │   │   ├── approval-config
│   │   │   │   │   ├── approval-config.component.html
│   │   │   │   │   ├── approval-config.component.scss
│   │   │   │   │   ├── approval-config.component.spec.ts
│   │   │   │   │   └── approval-config.component.ts
│   │   │   │   ├── asset-summary-widget
│   │   │   │   │   ├── asset-summary-widget.component.html
│   │   │   │   │   ├── asset-summary-widget.component.scss
│   │   │   │   │   ├── asset-summary-widget.component.spec.ts
│   │   │   │   │   └── asset-summary-widget.component.ts
│   │   │   │   ├── asset-value-panel-widget
│   │   │   │   │   ├── asset-value-panel-widget.component.html
│   │   │   │   │   ├── asset-value-panel-widget.component.scss
│   │   │   │   │   ├── asset-value-panel-widget.component.spec.ts
│   │   │   │   │   └── asset-value-panel-widget.component.ts
│   │   │   │   ├── assignee
│   │   │   │   │   ├── assignee.component.html
│   │   │   │   │   ├── assignee.component.scss
│   │   │   │   │   ├── assignee.component.spec.ts
│   │   │   │   │   └── assignee.component.ts
│   │   │   │   ├── associate-relation
│   │   │   │   │   ├── associate-relation.component.html
│   │   │   │   │   ├── associate-relation.component.scss
│   │   │   │   │   ├── associate-relation.component.spec.ts
│   │   │   │   │   └── associate-relation.component.ts
│   │   │   │   ├── attach-knowledge-base
│   │   │   │   │   ├── attach-knowledge-base.component.html
│   │   │   │   │   ├── attach-knowledge-base.component.scss
│   │   │   │   │   ├── attach-knowledge-base.component.spec.ts
│   │   │   │   │   └── attach-knowledge-base.component.ts
│   │   │   │   ├── basic-count-panel
│   │   │   │   │   ├── basic-count-panel.component.html
│   │   │   │   │   ├── basic-count-panel.component.scss
│   │   │   │   │   ├── basic-count-panel.component.spec.ts
│   │   │   │   │   └── basic-count-panel.component.ts
│   │   │   │   ├── bulk-tag
│   │   │   │   │   ├── bulk-tag.component.html
│   │   │   │   │   ├── bulk-tag.component.scss
│   │   │   │   │   ├── bulk-tag.component.spec.ts
│   │   │   │   │   └── bulk-tag.component.ts
│   │   │   │   ├── burger-menu
│   │   │   │   │   ├── burger-menu.component.html
│   │   │   │   │   ├── burger-menu.component.scss
│   │   │   │   │   ├── burger-menu.component.spec.ts
│   │   │   │   │   └── burger-menu.component.ts
│   │   │   │   ├── card-sekeleton
│   │   │   │   │   ├── card-sekeleton.component.html
│   │   │   │   │   ├── card-sekeleton.component.scss
│   │   │   │   │   ├── card-sekeleton.component.spec.ts
│   │   │   │   │   └── card-sekeleton.component.ts
│   │   │   │   ├── card-select
│   │   │   │   │   ├── card-select.component.html
│   │   │   │   │   ├── card-select.component.scss
│   │   │   │   │   ├── card-select.component.spec.ts
│   │   │   │   │   └── card-select.component.ts
│   │   │   │   ├── card-skeleton
│   │   │   │   │   ├── card-skeleton.component.html
│   │   │   │   │   ├── card-skeleton.component.scss
│   │   │   │   │   ├── card-skeleton.component.spec.ts
│   │   │   │   │   └── card-skeleton.component.ts
│   │   │   │   ├── change-count
│   │   │   │   │   ├── change-count.component.html
│   │   │   │   │   ├── change-count.component.scss
│   │   │   │   │   ├── change-count.component.spec.ts
│   │   │   │   │   └── change-count.component.ts
│   │   │   │   ├── change-summary
│   │   │   │   │   ├── change-summary.component.html
│   │   │   │   │   ├── change-summary.component.scss
│   │   │   │   │   ├── change-summary.component.spec.ts
│   │   │   │   │   └── change-summary.component.ts
│   │   │   │   ├── chat-content
│   │   │   │   │   ├── chat-content.component.html
│   │   │   │   │   ├── chat-content.component.scss
│   │   │   │   │   ├── chat-content.component.spec.ts
│   │   │   │   │   ├── chat-content.component.ts
│   │   │   │   │   └── chat.data.ts
│   │   │   │   ├── close-ticket-sidebar
│   │   │   │   │   ├── close-ticket-sidebar.component.html
│   │   │   │   │   ├── close-ticket-sidebar.component.scss
│   │   │   │   │   ├── close-ticket-sidebar.component.spec.ts
│   │   │   │   │   └── close-ticket-sidebar.component.ts
│   │   │   │   ├── common-panel-card-skeleton
│   │   │   │   │   ├── common-panel-card-skeleton.component.html
│   │   │   │   │   ├── common-panel-card-skeleton.component.scss
│   │   │   │   │   ├── common-panel-card-skeleton.component.spec.ts
│   │   │   │   │   └── common-panel-card-skeleton.component.ts
│   │   │   │   ├── common-pannel-view
│   │   │   │   │   ├── common-pannel-view.component.html
│   │   │   │   │   ├── common-pannel-view.component.scss
│   │   │   │   │   ├── common-pannel-view.component.spec.ts
│   │   │   │   │   └── common-pannel-view.component.ts
│   │   │   │   ├── common-problem-view
│   │   │   │   │   ├── common-problem-view.component.html
│   │   │   │   │   ├── common-problem-view.component.scss
│   │   │   │   │   ├── common-problem-view.component.spec.ts
│   │   │   │   │   └── common-problem-view.component.ts
│   │   │   │   ├── common-process-view-sidebar
│   │   │   │   │   ├── common-process-view-sidebar.component.html
│   │   │   │   │   ├── common-process-view-sidebar.component.scss
│   │   │   │   │   ├── common-process-view-sidebar.component.spec.ts
│   │   │   │   │   └── common-process-view-sidebar.component.ts
│   │   │   │   ├── common-smart-grid
│   │   │   │   │   ├── common-smart-grid.component.html
│   │   │   │   │   ├── common-smart-grid.component.scss
│   │   │   │   │   ├── common-smart-grid.component.spec.ts
│   │   │   │   │   └── common-smart-grid.component.ts
│   │   │   │   ├── common-view-task
│   │   │   │   │   ├── common-view-task.component.html
│   │   │   │   │   ├── common-view-task.component.scss
│   │   │   │   │   ├── common-view-task.component.spec.ts
│   │   │   │   │   └── common-view-task.component.ts
│   │   │   │   ├── consumable-summary-widget
│   │   │   │   │   ├── consumable-summary-widget.component.html
│   │   │   │   │   ├── consumable-summary-widget.component.scss
│   │   │   │   │   ├── consumable-summary-widget.component.spec.ts
│   │   │   │   │   └── consumable-summary-widget.component.ts
│   │   │   │   ├── contract-summary-widget
│   │   │   │   │   ├── contract-summary-widget.component.html
│   │   │   │   │   ├── contract-summary-widget.component.scss
│   │   │   │   │   ├── contract-summary-widget.component.spec.ts
│   │   │   │   │   └── contract-summary-widget.component.ts
│   │   │   │   ├── csv-uploader
│   │   │   │   │   ├── csv-upload-feature-routing.module.ts
│   │   │   │   │   ├── csv-upload-feature.component.html
│   │   │   │   │   ├── csv-upload-feature.component.scss
│   │   │   │   │   ├── csv-upload-feature.component.spec.ts
│   │   │   │   │   ├── csv-upload-feature.component.ts
│   │   │   │   │   └── csv-upload-feature.module.ts
│   │   │   │   ├── custom-category-list
│   │   │   │   │   ├── custom-category-list.component.html
│   │   │   │   │   ├── custom-category-list.component.scss
│   │   │   │   │   ├── custom-category-list.component.spec.ts
│   │   │   │   │   └── custom-category-list.component.ts
│   │   │   │   ├── custom-theme
│   │   │   │   │   ├── custom-theme-routing.module.ts
│   │   │   │   │   ├── custom-theme.component.html
│   │   │   │   │   ├── custom-theme.component.scss
│   │   │   │   │   ├── custom-theme.component.spec.ts
│   │   │   │   │   ├── custom-theme.component.ts
│   │   │   │   │   └── custom-theme.module.ts
│   │   │   │   ├── date-range-picker
│   │   │   │   │   ├── date-range-picker.component.html
│   │   │   │   │   ├── date-range-picker.component.scss
│   │   │   │   │   ├── date-range-picker.component.spec.ts
│   │   │   │   │   └── date-range-picker.component.ts
│   │   │   │   ├── device-summary
│   │   │   │   │   ├── device-summary.component.html
│   │   │   │   │   ├── device-summary.component.scss
│   │   │   │   │   ├── device-summary.component.spec.ts
│   │   │   │   │   └── device-summary.component.ts
│   │   │   │   ├── dns-add-task
│   │   │   │   │   ├── dns-add-task.component.html
│   │   │   │   │   ├── dns-add-task.component.scss
│   │   │   │   │   ├── dns-add-task.component.spec.ts
│   │   │   │   │   └── dns-add-task.component.ts
│   │   │   │   ├── dns-aging-timer
│   │   │   │   │   ├── dns-aging-timer.component.html
│   │   │   │   │   ├── dns-aging-timer.component.scss
│   │   │   │   │   ├── dns-aging-timer.component.spec.ts
│   │   │   │   │   └── dns-aging-timer.component.ts
│   │   │   │   ├── dns-asset-select
│   │   │   │   │   ├── dns-asset-select.component.html
│   │   │   │   │   ├── dns-asset-select.component.scss
│   │   │   │   │   ├── dns-asset-select.component.spec.ts
│   │   │   │   │   └── dns-asset-select.component.ts
│   │   │   │   ├── dns-attachment
│   │   │   │   │   ├── dns-attachment.component.html
│   │   │   │   │   ├── dns-attachment.component.scss
│   │   │   │   │   ├── dns-attachment.component.spec.ts
│   │   │   │   │   └── dns-attachment.component.ts
│   │   │   │   ├── dns-change-attachment
│   │   │   │   │   ├── dns-change-attachment.component.html
│   │   │   │   │   ├── dns-change-attachment.component.scss
│   │   │   │   │   ├── dns-change-attachment.component.spec.ts
│   │   │   │   │   └── dns-change-attachment.component.ts
│   │   │   │   ├── dns-change-close
│   │   │   │   │   ├── dns-change-close.component.html
│   │   │   │   │   ├── dns-change-close.component.scss
│   │   │   │   │   ├── dns-change-close.component.spec.ts
│   │   │   │   │   └── dns-change-close.component.ts
│   │   │   │   ├── dns-change-edit-sidebar
│   │   │   │   │   ├── dns-change-edit-sidebar.component.html
│   │   │   │   │   ├── dns-change-edit-sidebar.component.scss
│   │   │   │   │   ├── dns-change-edit-sidebar.component.spec.ts
│   │   │   │   │   └── dns-change-edit-sidebar.component.ts
│   │   │   │   ├── dns-change-impact
│   │   │   │   │   ├── dns-change-impact.component.html
│   │   │   │   │   ├── dns-change-impact.component.scss
│   │   │   │   │   ├── dns-change-impact.component.spec.ts
│   │   │   │   │   └── dns-change-impact.component.ts
│   │   │   │   ├── dns-change-incident-view
│   │   │   │   │   ├── dns-change-incident-view.component.html
│   │   │   │   │   ├── dns-change-incident-view.component.scss
│   │   │   │   │   ├── dns-change-incident-view.component.spec.ts
│   │   │   │   │   └── dns-change-incident-view.component.ts
│   │   │   │   ├── dns-change-risk
│   │   │   │   │   ├── dns-change-risk.component.html
│   │   │   │   │   ├── dns-change-risk.component.scss
│   │   │   │   │   ├── dns-change-risk.component.spec.ts
│   │   │   │   │   └── dns-change-risk.component.ts
│   │   │   │   ├── dns-change-to-incident
│   │   │   │   │   ├── dns-change-to-incident.component.html
│   │   │   │   │   ├── dns-change-to-incident.component.scss
│   │   │   │   │   ├── dns-change-to-incident.component.spec.ts
│   │   │   │   │   └── dns-change-to-incident.component.ts
│   │   │   │   ├── dns-change-view
│   │   │   │   │   ├── dns-change-view.component.html
│   │   │   │   │   ├── dns-change-view.component.scss
│   │   │   │   │   ├── dns-change-view.component.spec.ts
│   │   │   │   │   └── dns-change-view.component.ts
│   │   │   │   ├── dns-color-dropdown
│   │   │   │   │   ├── dns-color-dropdown.component.html
│   │   │   │   │   ├── dns-color-dropdown.component.scss
│   │   │   │   │   ├── dns-color-dropdown.component.spec.ts
│   │   │   │   │   └── dns-color-dropdown.component.ts
│   │   │   │   ├── dns-communication
│   │   │   │   │   ├── dns-communication.component.html
│   │   │   │   │   ├── dns-communication.component.scss
│   │   │   │   │   ├── dns-communication.component.spec.ts
│   │   │   │   │   └── dns-communication.component.ts
│   │   │   │   ├── dns-create-task
│   │   │   │   │   ├── dns-create-task.component.html
│   │   │   │   │   ├── dns-create-task.component.scss
│   │   │   │   │   ├── dns-create-task.component.spec.ts
│   │   │   │   │   └── dns-create-task.component.ts
│   │   │   │   ├── dns-custom-field
│   │   │   │   │   ├── dns-custom-field.component.html
│   │   │   │   │   ├── dns-custom-field.component.scss
│   │   │   │   │   ├── dns-custom-field.component.spec.ts
│   │   │   │   │   └── dns-custom-field.component.ts
│   │   │   │   ├── dns-edit-requester
│   │   │   │   │   ├── dns-edit-requester.component.html
│   │   │   │   │   ├── dns-edit-requester.component.scss
│   │   │   │   │   ├── dns-edit-requester.component.spec.ts
│   │   │   │   │   └── dns-edit-requester.component.ts
│   │   │   │   ├── dns-empty-grid-data
│   │   │   │   │   ├── dns-empty-grid-data.component.html
│   │   │   │   │   ├── dns-empty-grid-data.component.scss
│   │   │   │   │   ├── dns-empty-grid-data.component.spec.ts
│   │   │   │   │   └── dns-empty-grid-data.component.ts
│   │   │   │   ├── dns-error-validation
│   │   │   │   │   ├── dns-error-validation.component.html
│   │   │   │   │   ├── dns-error-validation.component.scss
│   │   │   │   │   ├── dns-error-validation.component.spec.ts
│   │   │   │   │   └── dns-error-validation.component.ts
│   │   │   │   ├── dns-grid
│   │   │   │   │   ├── dns-grid.component.html
│   │   │   │   │   ├── dns-grid.component.scss
│   │   │   │   │   ├── dns-grid.component.spec.ts
│   │   │   │   │   └── dns-grid.component.ts
│   │   │   │   ├── dns-grid-pipe
│   │   │   │   │   ├── dns-grid-pipe.component.html
│   │   │   │   │   ├── dns-grid-pipe.component.scss
│   │   │   │   │   ├── dns-grid-pipe.component.spec.ts
│   │   │   │   │   └── dns-grid-pipe.component.ts
│   │   │   │   ├── dns-grid-tag
│   │   │   │   │   ├── dns-grid-tag.component.html
│   │   │   │   │   ├── dns-grid-tag.component.scss
│   │   │   │   │   ├── dns-grid-tag.component.spec.ts
│   │   │   │   │   └── dns-grid-tag.component.ts
│   │   │   │   ├── dns-help
│   │   │   │   │   ├── dns-help.component.html
│   │   │   │   │   ├── dns-help.component.scss
│   │   │   │   │   ├── dns-help.component.spec.ts
│   │   │   │   │   ├── dns-help.component.ts
│   │   │   │   │   └── help.json
│   │   │   │   ├── dns-icon-view
│   │   │   │   │   ├── dns-icon-view.component.html
│   │   │   │   │   ├── dns-icon-view.component.scss
│   │   │   │   │   ├── dns-icon-view.component.spec.ts
│   │   │   │   │   └── dns-icon-view.component.ts
│   │   │   │   ├── dns-incident-edit-sidebar
│   │   │   │   │   ├── dns-incident-edit-sidebar.component.html
│   │   │   │   │   ├── dns-incident-edit-sidebar.component.scss
│   │   │   │   │   ├── dns-incident-edit-sidebar.component.spec.ts
│   │   │   │   │   └── dns-incident-edit-sidebar.component.ts
│   │   │   │   ├── dns-incident-kb-solution
│   │   │   │   │   ├── dns-incident-kb-solution.component.html
│   │   │   │   │   ├── dns-incident-kb-solution.component.scss
│   │   │   │   │   ├── dns-incident-kb-solution.component.spec.ts
│   │   │   │   │   └── dns-incident-kb-solution.component.ts
│   │   │   │   ├── dns-incident-request-view
│   │   │   │   │   ├── dns-incident-request-view.component.html
│   │   │   │   │   ├── dns-incident-request-view.component.scss
│   │   │   │   │   ├── dns-incident-request-view.component.spec.ts
│   │   │   │   │   └── dns-incident-request-view.component.ts
│   │   │   │   ├── dns-incident-to-change
│   │   │   │   │   ├── dns-incident-to-change.component.html
│   │   │   │   │   ├── dns-incident-to-change.component.scss
│   │   │   │   │   ├── dns-incident-to-change.component.spec.ts
│   │   │   │   │   └── dns-incident-to-change.component.ts
│   │   │   │   ├── dns-incident-to-problem
│   │   │   │   │   ├── dns-incident-to-problem.component.html
│   │   │   │   │   ├── dns-incident-to-problem.component.scss
│   │   │   │   │   ├── dns-incident-to-problem.component.spec.ts
│   │   │   │   │   └── dns-incident-to-problem.component.ts
│   │   │   │   ├── dns-incident-to-request
│   │   │   │   │   ├── dns-incident-to-request.component.html
│   │   │   │   │   ├── dns-incident-to-request.component.scss
│   │   │   │   │   ├── dns-incident-to-request.component.spec.ts
│   │   │   │   │   └── dns-incident-to-request.component.ts
│   │   │   │   ├── dns-incident-view-sidebar
│   │   │   │   │   ├── dns-incident-view-sidebar.component.html
│   │   │   │   │   ├── dns-incident-view-sidebar.component.scss
│   │   │   │   │   ├── dns-incident-view-sidebar.component.spec.ts
│   │   │   │   │   └── dns-incident-view-sidebar.component.ts
│   │   │   │   ├── dns-kb-add
│   │   │   │   │   ├── dns-kb-add.component.html
│   │   │   │   │   ├── dns-kb-add.component.scss
│   │   │   │   │   ├── dns-kb-add.component.spec.ts
│   │   │   │   │   └── dns-kb-add.component.ts
│   │   │   │   ├── dns-macro-selector
│   │   │   │   │   ├── dns-macro-selector.component.html
│   │   │   │   │   ├── dns-macro-selector.component.scss
│   │   │   │   │   ├── dns-macro-selector.component.spec.ts
│   │   │   │   │   └── dns-macro-selector.component.ts
│   │   │   │   ├── dns-msp-customer-dropdown
│   │   │   │   │   ├── dns-msp-customer-dropdown.component.html
│   │   │   │   │   ├── dns-msp-customer-dropdown.component.scss
│   │   │   │   │   ├── dns-msp-customer-dropdown.component.spec.ts
│   │   │   │   │   └── dns-msp-customer-dropdown.component.ts
│   │   │   │   ├── dns-notification-rule-card
│   │   │   │   │   ├── dns-notification-rule-card.component.html
│   │   │   │   │   ├── dns-notification-rule-card.component.scss
│   │   │   │   │   ├── dns-notification-rule-card.component.spec.ts
│   │   │   │   │   └── dns-notification-rule-card.component.ts
│   │   │   │   ├── dns-option-picker
│   │   │   │   │   ├── dns-option-picker.component.html
│   │   │   │   │   ├── dns-option-picker.component.scss
│   │   │   │   │   ├── dns-option-picker.component.spec.ts
│   │   │   │   │   └── dns-option-picker.component.ts
│   │   │   │   ├── dns-pagination
│   │   │   │   │   ├── dns-pagination.component.html
│   │   │   │   │   ├── dns-pagination.component.scss
│   │   │   │   │   ├── dns-pagination.component.spec.ts
│   │   │   │   │   └── dns-pagination.component.ts
│   │   │   │   ├── dns-panel-view
│   │   │   │   │   ├── dns-panel-view.component.html
│   │   │   │   │   ├── dns-panel-view.component.scss
│   │   │   │   │   ├── dns-panel-view.component.spec.ts
│   │   │   │   │   └── dns-panel-view.component.ts
│   │   │   │   ├── dns-problem-analysis-sidebar
│   │   │   │   │   ├── dns-problem-analysis-sidebar.component.html
│   │   │   │   │   ├── dns-problem-analysis-sidebar.component.scss
│   │   │   │   │   ├── dns-problem-analysis-sidebar.component.spec.ts
│   │   │   │   │   └── dns-problem-analysis-sidebar.component.ts
│   │   │   │   ├── dns-problem-attachment
│   │   │   │   │   ├── dns-problem-attachment.component.html
│   │   │   │   │   ├── dns-problem-attachment.component.scss
│   │   │   │   │   ├── dns-problem-attachment.component.spec.ts
│   │   │   │   │   └── dns-problem-attachment.component.ts
│   │   │   │   ├── dns-problem-close
│   │   │   │   │   ├── dns-problem-close.component.html
│   │   │   │   │   ├── dns-problem-close.component.scss
│   │   │   │   │   ├── dns-problem-close.component.spec.ts
│   │   │   │   │   └── dns-problem-close.component.ts
│   │   │   │   ├── dns-problem-edit-sidebar
│   │   │   │   │   ├── dns-problem-edit-sidebar.component.html
│   │   │   │   │   ├── dns-problem-edit-sidebar.component.scss
│   │   │   │   │   ├── dns-problem-edit-sidebar.component.spec.ts
│   │   │   │   │   └── dns-problem-edit-sidebar.component.ts
│   │   │   │   ├── dns-problem-incident-view
│   │   │   │   │   ├── dns-problem-incident-view.component.html
│   │   │   │   │   ├── dns-problem-incident-view.component.scss
│   │   │   │   │   ├── dns-problem-incident-view.component.spec.ts
│   │   │   │   │   └── dns-problem-incident-view.component.ts
│   │   │   │   ├── dns-problem-resolve
│   │   │   │   │   ├── dns-problem-resolve.component.html
│   │   │   │   │   ├── dns-problem-resolve.component.scss
│   │   │   │   │   ├── dns-problem-resolve.component.spec.ts
│   │   │   │   │   └── dns-problem-resolve.component.ts
│   │   │   │   ├── dns-problem-solution-sidebar
│   │   │   │   │   ├── dns-problem-solution-sidebar.component.html
│   │   │   │   │   ├── dns-problem-solution-sidebar.component.scss
│   │   │   │   │   ├── dns-problem-solution-sidebar.component.spec.ts
│   │   │   │   │   └── dns-problem-solution-sidebar.component.ts
│   │   │   │   ├── dns-problem-to-change
│   │   │   │   │   ├── dns-problem-to-change.component.html
│   │   │   │   │   ├── dns-problem-to-change.component.scss
│   │   │   │   │   ├── dns-problem-to-change.component.spec.ts
│   │   │   │   │   └── dns-problem-to-change.component.ts
│   │   │   │   ├── dns-problem-to-incident
│   │   │   │   │   ├── dns-problem-to-incident.component.html
│   │   │   │   │   ├── dns-problem-to-incident.component.scss
│   │   │   │   │   ├── dns-problem-to-incident.component.spec.ts
│   │   │   │   │   └── dns-problem-to-incident.component.ts
│   │   │   │   ├── dns-problem-view-draft-sidebar
│   │   │   │   │   ├── dns-problem-view-draft-sidebar.component.html
│   │   │   │   │   ├── dns-problem-view-draft-sidebar.component.scss
│   │   │   │   │   ├── dns-problem-view-draft-sidebar.component.spec.ts
│   │   │   │   │   └── dns-problem-view-draft-sidebar.component.ts
│   │   │   │   ├── dns-progress-timer-component
│   │   │   │   │   ├── dns-progress-timer-component.component.html
│   │   │   │   │   ├── dns-progress-timer-component.component.scss
│   │   │   │   │   ├── dns-progress-timer-component.component.spec.ts
│   │   │   │   │   └── dns-progress-timer-component.component.ts
│   │   │   │   ├── dns-rating
│   │   │   │   │   ├── dns-rating.component.html
│   │   │   │   │   ├── dns-rating.component.scss
│   │   │   │   │   ├── dns-rating.component.spec.ts
│   │   │   │   │   └── dns-rating.component.ts
│   │   │   │   ├── dns-release-add-task
│   │   │   │   │   ├── dns-release-add-task.component.html
│   │   │   │   │   ├── dns-release-add-task.component.scss
│   │   │   │   │   ├── dns-release-add-task.component.spec.ts
│   │   │   │   │   └── dns-release-add-task.component.ts
│   │   │   │   ├── dns-release-attachment
│   │   │   │   │   ├── dns-release-attachment.component.html
│   │   │   │   │   ├── dns-release-attachment.component.scss
│   │   │   │   │   ├── dns-release-attachment.component.spec.ts
│   │   │   │   │   └── dns-release-attachment.component.ts
│   │   │   │   ├── dns-release-close
│   │   │   │   │   ├── dns-release-close.component.html
│   │   │   │   │   ├── dns-release-close.component.scss
│   │   │   │   │   ├── dns-release-close.component.spec.ts
│   │   │   │   │   └── dns-release-close.component.ts
│   │   │   │   ├── dns-release-edit-sidebar
│   │   │   │   │   ├── dns-release-edit-sidebar.component.html
│   │   │   │   │   ├── dns-release-edit-sidebar.component.scss
│   │   │   │   │   ├── dns-release-edit-sidebar.component.spec.ts
│   │   │   │   │   └── dns-release-edit-sidebar.component.ts
│   │   │   │   ├── dns-release-related-task
│   │   │   │   │   ├── dns-release-related-task.component.html
│   │   │   │   │   ├── dns-release-related-task.component.scss
│   │   │   │   │   ├── dns-release-related-task.component.spec.ts
│   │   │   │   │   └── dns-release-related-task.component.ts
│   │   │   │   ├── dns-release-view-task
│   │   │   │   │   ├── dns-release-view-task.component.html
│   │   │   │   │   ├── dns-release-view-task.component.scss
│   │   │   │   │   ├── dns-release-view-task.component.spec.ts
│   │   │   │   │   └── dns-release-view-task.component.ts
│   │   │   │   ├── dns-request-attachment
│   │   │   │   │   ├── dns-request-attachment.component.html
│   │   │   │   │   ├── dns-request-attachment.component.scss
│   │   │   │   │   ├── dns-request-attachment.component.spec.ts
│   │   │   │   │   └── dns-request-attachment.component.ts
│   │   │   │   ├── dns-request-close
│   │   │   │   │   ├── dns-request-close.component.html
│   │   │   │   │   ├── dns-request-close.component.scss
│   │   │   │   │   ├── dns-request-close.component.spec.ts
│   │   │   │   │   └── dns-request-close.component.ts
│   │   │   │   ├── dns-request-edit-sidebar
│   │   │   │   │   ├── dns-request-edit-sidebar.component.html
│   │   │   │   │   ├── dns-request-edit-sidebar.component.scss
│   │   │   │   │   ├── dns-request-edit-sidebar.component.spec.ts
│   │   │   │   │   └── dns-request-edit-sidebar.component.ts
│   │   │   │   ├── dns-request-incident-view
│   │   │   │   │   ├── dns-request-incident-view.component.html
│   │   │   │   │   ├── dns-request-incident-view.component.scss
│   │   │   │   │   ├── dns-request-incident-view.component.spec.ts
│   │   │   │   │   └── dns-request-incident-view.component.ts
│   │   │   │   ├── dns-request-resolve
│   │   │   │   │   ├── dns-request-resolve.component.html
│   │   │   │   │   ├── dns-request-resolve.component.scss
│   │   │   │   │   ├── dns-request-resolve.component.spec.ts
│   │   │   │   │   └── dns-request-resolve.component.ts
│   │   │   │   ├── dns-request-to-change
│   │   │   │   │   ├── dns-request-to-change.component.html
│   │   │   │   │   ├── dns-request-to-change.component.scss
│   │   │   │   │   ├── dns-request-to-change.component.spec.ts
│   │   │   │   │   └── dns-request-to-change.component.ts
│   │   │   │   ├── dns-request-to-incident
│   │   │   │   │   ├── dns-request-to-incident.component.html
│   │   │   │   │   ├── dns-request-to-incident.component.scss
│   │   │   │   │   ├── dns-request-to-incident.component.spec.ts
│   │   │   │   │   └── dns-request-to-incident.component.ts
│   │   │   │   ├── dns-resolve-status
│   │   │   │   │   ├── dns-resolve-status.component.html
│   │   │   │   │   ├── dns-resolve-status.component.scss
│   │   │   │   │   ├── dns-resolve-status.component.spec.ts
│   │   │   │   │   └── dns-resolve-status.component.ts
│   │   │   │   ├── dns-service-form
│   │   │   │   │   ├── dns-service-form.component.html
│   │   │   │   │   ├── dns-service-form.component.scss
│   │   │   │   │   ├── dns-service-form.component.spec.ts
│   │   │   │   │   └── dns-service-form.component.ts
│   │   │   │   ├── dns-sidebar
│   │   │   │   │   ├── dns-sidebar.component.html
│   │   │   │   │   ├── dns-sidebar.component.scss
│   │   │   │   │   ├── dns-sidebar.component.spec.ts
│   │   │   │   │   └── dns-sidebar.component.ts
│   │   │   │   ├── dns-sla-info-card
│   │   │   │   │   ├── dns-sla-info-card.component.html
│   │   │   │   │   ├── dns-sla-info-card.component.scss
│   │   │   │   │   ├── dns-sla-info-card.component.spec.ts
│   │   │   │   │   └── dns-sla-info-card.component.ts
│   │   │   │   ├── dns-sla-timer
│   │   │   │   │   ├── dns-sla-timer.component.html
│   │   │   │   │   ├── dns-sla-timer.component.scss
│   │   │   │   │   ├── dns-sla-timer.component.spec.ts
│   │   │   │   │   └── dns-sla-timer.component.ts
│   │   │   │   ├── dns-smart-grid
│   │   │   │   │   ├── dns-smart-grid.component.html
│   │   │   │   │   ├── dns-smart-grid.component.scss
│   │   │   │   │   ├── dns-smart-grid.component.spec.ts
│   │   │   │   │   └── dns-smart-grid.component.ts
│   │   │   │   ├── dns-sms-config
│   │   │   │   │   ├── dns-sms-config.component.html
│   │   │   │   │   ├── dns-sms-config.component.scss
│   │   │   │   │   ├── dns-sms-config.component.spec.ts
│   │   │   │   │   └── dns-sms-config.component.ts
│   │   │   │   ├── dns-stage-representation
│   │   │   │   │   ├── dns-stage-representation.component.html
│   │   │   │   │   ├── dns-stage-representation.component.scss
│   │   │   │   │   ├── dns-stage-representation.component.spec.ts
│   │   │   │   │   └── dns-stage-representation.component.ts
│   │   │   │   ├── dns-table-count
│   │   │   │   │   ├── dns-table-count.component.html
│   │   │   │   │   ├── dns-table-count.component.scss
│   │   │   │   │   ├── dns-table-count.component.spec.ts
│   │   │   │   │   └── dns-table-count.component.ts
│   │   │   │   ├── dns-tags
│   │   │   │   │   ├── dns-tags.component.html
│   │   │   │   │   ├── dns-tags.component.scss
│   │   │   │   │   ├── dns-tags.component.spec.ts
│   │   │   │   │   └── dns-tags.component.ts
│   │   │   │   ├── dns-threshold-color-selector
│   │   │   │   │   ├── dns-threshold-color-selector.component.html
│   │   │   │   │   ├── dns-threshold-color-selector.component.scss
│   │   │   │   │   ├── dns-threshold-color-selector.component.spec.ts
│   │   │   │   │   └── dns-threshold-color-selector.component.ts
│   │   │   │   ├── dns-value-selector
│   │   │   │   │   ├── dns-value-selector.component.html
│   │   │   │   │   ├── dns-value-selector.component.scss
│   │   │   │   │   ├── dns-value-selector.component.spec.ts
│   │   │   │   │   └── dns-value-selector.component.ts
│   │   │   │   ├── dns-view-task
│   │   │   │   │   ├── dns-view-task.component.html
│   │   │   │   │   ├── dns-view-task.component.scss
│   │   │   │   │   ├── dns-view-task.component.spec.ts
│   │   │   │   │   └── dns-view-task.component.ts
│   │   │   │   ├── dns-workflow
│   │   │   │   │   ├── dns-workflow.component.html
│   │   │   │   │   ├── dns-workflow.component.scss
│   │   │   │   │   ├── dns-workflow.component.spec.ts
│   │   │   │   │   └── dns-workflow.component.ts
│   │   │   │   ├── download-progress-button
│   │   │   │   │   ├── download-progress-button.component.html
│   │   │   │   │   ├── download-progress-button.component.scss
│   │   │   │   │   ├── download-progress-button.component.spec.ts
│   │   │   │   │   └── download-progress-button.component.ts
│   │   │   │   ├── dynamic-dropdown
│   │   │   │   │   ├── dynamic-dropdown.component.html
│   │   │   │   │   ├── dynamic-dropdown.component.scss
│   │   │   │   │   ├── dynamic-dropdown.component.spec.ts
│   │   │   │   │   └── dynamic-dropdown.component.ts
│   │   │   │   ├── editable-select
│   │   │   │   │   ├── editable-select-routing.module.ts
│   │   │   │   │   ├── editable-select.component.html
│   │   │   │   │   ├── editable-select.component.scss
│   │   │   │   │   ├── editable-select.component.spec.ts
│   │   │   │   │   ├── editable-select.component.ts
│   │   │   │   │   └── editable-select.module.ts
│   │   │   │   ├── email-feature
│   │   │   │   │   ├── email-feature.component.html
│   │   │   │   │   ├── email-feature.component.scss
│   │   │   │   │   ├── email-feature.component.spec.ts
│   │   │   │   │   └── email-feature.component.ts
│   │   │   │   ├── event-count
│   │   │   │   │   ├── event-count.component.html
│   │   │   │   │   ├── event-count.component.scss
│   │   │   │   │   ├── event-count.component.spec.ts
│   │   │   │   │   └── event-count.component.ts
│   │   │   │   ├── event-summary
│   │   │   │   │   ├── event-summary.component.html
│   │   │   │   │   ├── event-summary.component.scss
│   │   │   │   │   ├── event-summary.component.spec.ts
│   │   │   │   │   └── event-summary.component.ts
│   │   │   │   ├── expected-assingee-sidebar
│   │   │   │   │   ├── expected-assingee-sidebar.component.html
│   │   │   │   │   ├── expected-assingee-sidebar.component.scss
│   │   │   │   │   ├── expected-assingee-sidebar.component.spec.ts
│   │   │   │   │   └── expected-assingee-sidebar.component.ts
│   │   │   │   ├── feedback-raiting-popover
│   │   │   │   │   ├── feedback-raiting-popover.component.html
│   │   │   │   │   ├── feedback-raiting-popover.component.scss
│   │   │   │   │   ├── feedback-raiting-popover.component.spec.ts
│   │   │   │   │   └── feedback-raiting-popover.component.ts
│   │   │   │   ├── filter-bar
│   │   │   │   │   ├── filter-bar.component.html
│   │   │   │   │   ├── filter-bar.component.scss
│   │   │   │   │   ├── filter-bar.component.spec.ts
│   │   │   │   │   └── filter-bar.component.ts
│   │   │   │   ├── getting-started-sidebar
│   │   │   │   │   ├── getting-started-sidebar.component.html
│   │   │   │   │   ├── getting-started-sidebar.component.scss
│   │   │   │   │   ├── getting-started-sidebar.component.spec.ts
│   │   │   │   │   └── getting-started-sidebar.component.ts
│   │   │   │   ├── grid-cell-card
│   │   │   │   │   ├── grid-cell-card.component.html
│   │   │   │   │   ├── grid-cell-card.component.scss
│   │   │   │   │   ├── grid-cell-card.component.spec.ts
│   │   │   │   │   └── grid-cell-card.component.ts
│   │   │   │   ├── grid-name-avatar
│   │   │   │   │   ├── grid-name-avatar.component.html
│   │   │   │   │   ├── grid-name-avatar.component.scss
│   │   │   │   │   ├── grid-name-avatar.component.spec.ts
│   │   │   │   │   └── grid-name-avatar.component.ts
│   │   │   │   ├── grid-name-design
│   │   │   │   │   ├── grid-name-design.component.html
│   │   │   │   │   ├── grid-name-design.component.scss
│   │   │   │   │   ├── grid-name-design.component.spec.ts
│   │   │   │   │   └── grid-name-design.component.ts
│   │   │   │   ├── grid-organization-name-design
│   │   │   │   │   ├── grid-organization-name-design.component.html
│   │   │   │   │   ├── grid-organization-name-design.component.scss
│   │   │   │   │   ├── grid-organization-name-design.component.spec.ts
│   │   │   │   │   └── grid-organization-name-design.component.ts
│   │   │   │   ├── grid-sekeleton
│   │   │   │   │   ├── grid-sekeleton.component.html
│   │   │   │   │   ├── grid-sekeleton.component.scss
│   │   │   │   │   ├── grid-sekeleton.component.spec.ts
│   │   │   │   │   └── grid-sekeleton.component.ts
│   │   │   │   ├── grid-skeleton
│   │   │   │   │   ├── grid-skeleton.component.html
│   │   │   │   │   ├── grid-skeleton.component.scss
│   │   │   │   │   ├── grid-skeleton.component.spec.ts
│   │   │   │   │   └── grid-skeleton.component.ts
│   │   │   │   ├── history-table
│   │   │   │   │   ├── history-table.component.html
│   │   │   │   │   ├── history-table.component.scss
│   │   │   │   │   ├── history-table.component.spec.ts
│   │   │   │   │   └── history-table.component.ts
│   │   │   │   ├── imacd-count
│   │   │   │   │   ├── imacd-count.component.html
│   │   │   │   │   ├── imacd-count.component.scss
│   │   │   │   │   ├── imacd-count.component.spec.ts
│   │   │   │   │   └── imacd-count.component.ts
│   │   │   │   ├── imacd-summary-widget
│   │   │   │   │   ├── imacd-summary-widget.component.html
│   │   │   │   │   ├── imacd-summary-widget.component.scss
│   │   │   │   │   ├── imacd-summary-widget.component.spec.ts
│   │   │   │   │   └── imacd-summary-widget.component.ts
│   │   │   │   ├── img-upload-feature
│   │   │   │   │   ├── image-cropper
│   │   │   │   │   │   ├── component
│   │   │   │   │   │   │   ├── image-cropper.component.html
│   │   │   │   │   │   │   ├── image-cropper.component.scss
│   │   │   │   │   │   │   └── image-cropper.component.ts
│   │   │   │   │   │   ├── image-cropper.module.ts
│   │   │   │   │   │   ├── interfaces
│   │   │   │   │   │   │   ├── cropper-position.interface.ts
│   │   │   │   │   │   │   ├── dimensions.interface.ts
│   │   │   │   │   │   │   ├── exif-transform.interface.ts
│   │   │   │   │   │   │   ├── image-cropped-event.interface.ts
│   │   │   │   │   │   │   ├── image-transform.interface.ts
│   │   │   │   │   │   │   ├── index.ts
│   │   │   │   │   │   │   └── move-start.interface.ts
│   │   │   │   │   │   └── utils
│   │   │   │   │   │       ├── blob.utils.ts
│   │   │   │   │   │       ├── exif.utils.ts
│   │   │   │   │   │       ├── hammer.utils.ts
│   │   │   │   │   │       └── resize.utils.ts
│   │   │   │   │   ├── img-upload-feature-routing.module.ts
│   │   │   │   │   ├── img-upload-feature.component.html
│   │   │   │   │   ├── img-upload-feature.component.scss
│   │   │   │   │   ├── img-upload-feature.component.spec.ts
│   │   │   │   │   ├── img-upload-feature.component.ts
│   │   │   │   │   └── img-upload-feature.module.ts
│   │   │   │   ├── incident-count-card
│   │   │   │   │   ├── incident-count.component.html
│   │   │   │   │   ├── incident-count.component.scss
│   │   │   │   │   ├── incident-count.component.spec.ts
│   │   │   │   │   └── incident-count.component.ts
│   │   │   │   ├── incident-summary
│   │   │   │   │   ├── incident-summary.component.html
│   │   │   │   │   ├── incident-summary.component.scss
│   │   │   │   │   ├── incident-summary.component.spec.ts
│   │   │   │   │   └── incident-summary.component.ts
│   │   │   │   ├── infi-attachment
│   │   │   │   │   ├── infi-attachment.component.html
│   │   │   │   │   ├── infi-attachment.component.scss
│   │   │   │   │   ├── infi-attachment.component.spec.ts
│   │   │   │   │   └── infi-attachment.component.ts
│   │   │   │   ├── infraon-call
│   │   │   │   │   ├── infraon-call.component.html
│   │   │   │   │   ├── infraon-call.component.scss
│   │   │   │   │   ├── infraon-call.component.spec.ts
│   │   │   │   │   └── infraon-call.component.ts
│   │   │   │   ├── inventory-count
│   │   │   │   │   ├── inventory-count.component.html
│   │   │   │   │   ├── inventory-count.component.scss
│   │   │   │   │   ├── inventory-count.component.spec.ts
│   │   │   │   │   └── inventory-count.component.ts
│   │   │   │   ├── kb-solution-view
│   │   │   │   │   ├── kb-solution-view.component.html
│   │   │   │   │   ├── kb-solution-view.component.scss
│   │   │   │   │   ├── kb-solution-view.component.spec.ts
│   │   │   │   │   └── kb-solution-view.component.ts
│   │   │   │   ├── location-design
│   │   │   │   │   ├── location-design.component.html
│   │   │   │   │   ├── location-design.component.scss
│   │   │   │   │   ├── location-design.component.spec.ts
│   │   │   │   │   └── location-design.component.ts
│   │   │   │   ├── macros-modal
│   │   │   │   │   ├── macros-modal.component.html
│   │   │   │   │   ├── macros-modal.component.scss
│   │   │   │   │   ├── macros-modal.component.spec.ts
│   │   │   │   │   └── macros-modal.component.ts
│   │   │   │   ├── micro-chart
│   │   │   │   │   ├── micro-chart.component.html
│   │   │   │   │   ├── micro-chart.component.scss
│   │   │   │   │   ├── micro-chart.component.spec.ts
│   │   │   │   │   └── micro-chart.component.ts
│   │   │   │   ├── msp-customer-column
│   │   │   │   │   ├── msp-customer-column.component.html
│   │   │   │   │   ├── msp-customer-column.component.scss
│   │   │   │   │   ├── msp-customer-column.component.spec.ts
│   │   │   │   │   └── msp-customer-column.component.ts
│   │   │   │   ├── multiple-charts
│   │   │   │   │   ├── multiple-charts.component.html
│   │   │   │   │   ├── multiple-charts.component.scss
│   │   │   │   │   ├── multiple-charts.component.spec.ts
│   │   │   │   │   └── multiple-charts.component.ts
│   │   │   │   ├── multiselect-tree-dropdown
│   │   │   │   │   ├── multiselect-tree-dropdown.component.html
│   │   │   │   │   ├── multiselect-tree-dropdown.component.scss
│   │   │   │   │   ├── multiselect-tree-dropdown.component.spec.ts
│   │   │   │   │   └── multiselect-tree-dropdown.component.ts
│   │   │   │   ├── mx-graph
│   │   │   │   │   ├── mx-graph.component.html
│   │   │   │   │   ├── mx-graph.component.scss
│   │   │   │   │   ├── mx-graph.component.spec.ts
│   │   │   │   │   └── mx-graph.component.ts
│   │   │   │   ├── network-diagram-widget
│   │   │   │   │   ├── network-diagram-widget.component.html
│   │   │   │   │   ├── network-diagram-widget.component.scss
│   │   │   │   │   ├── network-diagram-widget.component.spec.ts
│   │   │   │   │   └── network-diagram-widget.component.ts
│   │   │   │   ├── ngx-dropdown-treeview-select
│   │   │   │   │   ├── dropdown-treeview-select-i18n.ts
│   │   │   │   │   ├── ngx-dropdown-treeview-select.component.html
│   │   │   │   │   ├── ngx-dropdown-treeview-select.component.scss
│   │   │   │   │   ├── ngx-dropdown-treeview-select.component.spec.ts
│   │   │   │   │   ├── ngx-dropdown-treeview-select.component.ts
│   │   │   │   │   └── ngx-dropdown-treeview.module.ts
│   │   │   │   ├── open-layers
│   │   │   │   │   ├── open-layers.component.html
│   │   │   │   │   ├── open-layers.component.scss
│   │   │   │   │   ├── open-layers.component.spec.ts
│   │   │   │   │   └── open-layers.component.ts
│   │   │   │   ├── panel-card-view
│   │   │   │   │   ├── panel-card-view.component.html
│   │   │   │   │   ├── panel-card-view.component.scss
│   │   │   │   │   ├── panel-card-view.component.spec.ts
│   │   │   │   │   └── panel-card-view.component.ts
│   │   │   │   ├── panel-status-widget
│   │   │   │   │   ├── panel-status-widget.component.html
│   │   │   │   │   ├── panel-status-widget.component.scss
│   │   │   │   │   ├── panel-status-widget.component.spec.ts
│   │   │   │   │   └── panel-status-widget.component.ts
│   │   │   │   ├── panel-view-widget
│   │   │   │   │   ├── panel-view-widget.component.html
│   │   │   │   │   ├── panel-view-widget.component.scss
│   │   │   │   │   ├── panel-view-widget.component.spec.ts
│   │   │   │   │   └── panel-view-widget.component.ts
│   │   │   │   ├── pannel-view-skeleton
│   │   │   │   │   ├── pannel-view-skeleton.component.html
│   │   │   │   │   ├── pannel-view-skeleton.component.scss
│   │   │   │   │   ├── pannel-view-skeleton.component.spec.ts
│   │   │   │   │   └── pannel-view-skeleton.component.ts
│   │   │   │   ├── planning-tab
│   │   │   │   │   ├── planning-tab.component.html
│   │   │   │   │   ├── planning-tab.component.scss
│   │   │   │   │   ├── planning-tab.component.spec.ts
│   │   │   │   │   └── planning-tab.component.ts
│   │   │   │   ├── presentation
│   │   │   │   │   ├── presentation.component.html
│   │   │   │   │   ├── presentation.component.scss
│   │   │   │   │   ├── presentation.component.spec.ts
│   │   │   │   │   └── presentation.component.ts
│   │   │   │   ├── pretty-select
│   │   │   │   │   ├── pretty-select.component.html
│   │   │   │   │   ├── pretty-select.component.scss
│   │   │   │   │   ├── pretty-select.component.spec.ts
│   │   │   │   │   └── pretty-select.component.ts
│   │   │   │   ├── priority-change
│   │   │   │   │   ├── priority-change.component.html
│   │   │   │   │   ├── priority-change.component.scss
│   │   │   │   │   ├── priority-change.component.spec.ts
│   │   │   │   │   └── priority-change.component.ts
│   │   │   │   ├── problem-count
│   │   │   │   │   ├── problem-count.component.html
│   │   │   │   │   ├── problem-count.component.scss
│   │   │   │   │   ├── problem-count.component.spec.ts
│   │   │   │   │   └── problem-count.component.ts
│   │   │   │   ├── problem-summary
│   │   │   │   │   ├── problem-summary.component.html
│   │   │   │   │   ├── problem-summary.component.scss
│   │   │   │   │   ├── problem-summary.component.spec.ts
│   │   │   │   │   └── problem-summary.component.ts
│   │   │   │   ├── process-relations
│   │   │   │   │   ├── process-relations.component.html
│   │   │   │   │   ├── process-relations.component.scss
│   │   │   │   │   ├── process-relations.component.spec.ts
│   │   │   │   │   └── process-relations.component.ts
│   │   │   │   ├── profile-avatar
│   │   │   │   │   ├── components
│   │   │   │   │   │   └── profile-avatar
│   │   │   │   │   │       ├── profile-avatar.component.html
│   │   │   │   │   │       ├── profile-avatar.component.scss
│   │   │   │   │   │       ├── profile-avatar.component.spec.ts
│   │   │   │   │   │       └── profile-avatar.component.ts
│   │   │   │   │   ├── profile-avatar-routing.module.ts
│   │   │   │   │   └── profile-avatar.module.ts
│   │   │   │   ├── radio-button-progressbar
│   │   │   │   │   ├── radio-button-progressbar.component.html
│   │   │   │   │   ├── radio-button-progressbar.component.scss
│   │   │   │   │   ├── radio-button-progressbar.component.spec.ts
│   │   │   │   │   └── radio-button-progressbar.component.ts
│   │   │   │   ├── release-count
│   │   │   │   │   ├── release-count.component.html
│   │   │   │   │   ├── release-count.component.scss
│   │   │   │   │   ├── release-count.component.spec.ts
│   │   │   │   │   └── release-count.component.ts
│   │   │   │   ├── release-summary
│   │   │   │   │   ├── release-summary.component.html
│   │   │   │   │   ├── release-summary.component.scss
│   │   │   │   │   ├── release-summary.component.spec.ts
│   │   │   │   │   └── release-summary.component.ts
│   │   │   │   ├── request-process-count-card
│   │   │   │   │   ├── request-process-count.component.html
│   │   │   │   │   ├── request-process-count.component.scss
│   │   │   │   │   ├── request-process-count.component.spec.ts
│   │   │   │   │   └── request-process-count.component.ts
│   │   │   │   ├── request-process-summary
│   │   │   │   │   ├── request-process-summary.component.html
│   │   │   │   │   ├── request-process-summary.component.scss
│   │   │   │   │   ├── request-process-summary.component.spec.ts
│   │   │   │   │   └── request-process-summary.component.ts
│   │   │   │   ├── requester-calling-modal
│   │   │   │   │   ├── requester-calling-modal.component.html
│   │   │   │   │   ├── requester-calling-modal.component.scss
│   │   │   │   │   ├── requester-calling-modal.component.spec.ts
│   │   │   │   │   └── requester-calling-modal.component.ts
│   │   │   │   ├── risk-tab
│   │   │   │   │   ├── risk-tab.component.html
│   │   │   │   │   ├── risk-tab.component.scss
│   │   │   │   │   ├── risk-tab.component.spec.ts
│   │   │   │   │   └── risk-tab.component.ts
│   │   │   │   ├── round-chart-card
│   │   │   │   │   ├── round-chart-card.component.html
│   │   │   │   │   ├── round-chart-card.component.scss
│   │   │   │   │   ├── round-chart-card.component.spec.ts
│   │   │   │   │   └── round-chart-card.component.ts
│   │   │   │   ├── search
│   │   │   │   │   ├── search.component.html
│   │   │   │   │   ├── search.component.scss
│   │   │   │   │   ├── search.component.spec.ts
│   │   │   │   │   └── search.component.ts
│   │   │   │   ├── select-badge
│   │   │   │   │   ├── select-badge.component.html
│   │   │   │   │   ├── select-badge.component.scss
│   │   │   │   │   ├── select-badge.component.spec.ts
│   │   │   │   │   └── select-badge.component.ts
│   │   │   │   ├── select-feature
│   │   │   │   │   ├── select-feature-routing.module.ts
│   │   │   │   │   ├── select-feature.component.html
│   │   │   │   │   ├── select-feature.component.scss
│   │   │   │   │   ├── select-feature.component.spec.ts
│   │   │   │   │   ├── select-feature.component.ts
│   │   │   │   │   ├── select-feature.module.ts
│   │   │   │   │   └── select.options.ts
│   │   │   │   ├── select-team
│   │   │   │   │   ├── select-team.component.html
│   │   │   │   │   ├── select-team.component.scss
│   │   │   │   │   ├── select-team.component.spec.ts
│   │   │   │   │   └── select-team.component.ts
│   │   │   │   ├── service-change
│   │   │   │   │   ├── service-change.component.html
│   │   │   │   │   ├── service-change.component.scss
│   │   │   │   │   ├── service-change.component.spec.ts
│   │   │   │   │   └── service-change.component.ts
│   │   │   │   ├── simple-table
│   │   │   │   │   └── panel-view-widget
│   │   │   │   │       ├── simple-table.component.html
│   │   │   │   │       ├── simple-table.component.scss
│   │   │   │   │       ├── simple-table.component.spec.ts
│   │   │   │   │       └── simple-table.component.ts
│   │   │   │   ├── simple-table-spi_npi
│   │   │   │   │   ├── simple-table-spi_npi.component.html
│   │   │   │   │   ├── simple-table-spi_npi.component.scss
│   │   │   │   │   ├── simple-table-spi_npi.component.spec.ts
│   │   │   │   │   └── simple-table-spi_npi.component.ts
│   │   │   │   ├── single-tree-dropdown
│   │   │   │   │   ├── single-tree-dropdown.component.html
│   │   │   │   │   ├── single-tree-dropdown.component.scss
│   │   │   │   │   ├── single-tree-dropdown.component.spec.ts
│   │   │   │   │   ├── single-tree-dropdown.component.ts
│   │   │   │   │   ├── tree-data.service.spec.ts
│   │   │   │   │   └── tree-data.service.ts
│   │   │   │   ├── sla-business-card
│   │   │   │   │   ├── sla-business-card.component.html
│   │   │   │   │   ├── sla-business-card.component.scss
│   │   │   │   │   ├── sla-business-card.component.spec.ts
│   │   │   │   │   └── sla-business-card.component.ts
│   │   │   │   ├── sla-metric-card
│   │   │   │   │   ├── sla-metric-card.component.html
│   │   │   │   │   ├── sla-metric-card.component.scss
│   │   │   │   │   ├── sla-metric-card.component.spec.ts
│   │   │   │   │   └── sla-metric-card.component.ts
│   │   │   │   ├── sla-metric-detail-sidebar
│   │   │   │   │   ├── sla-metric-detail-sidebar.component.html
│   │   │   │   │   ├── sla-metric-detail-sidebar.component.scss
│   │   │   │   │   ├── sla-metric-detail-sidebar.component.spec.ts
│   │   │   │   │   └── sla-metric-detail-sidebar.component.ts
│   │   │   │   ├── sla-response-count
│   │   │   │   │   ├── sla-response-count.component.html
│   │   │   │   │   ├── sla-response-count.component.scss
│   │   │   │   │   ├── sla-response-count.component.spec.ts
│   │   │   │   │   └── sla-response-count.component.ts
│   │   │   │   ├── sms
│   │   │   │   │   ├── sms.component.html
│   │   │   │   │   ├── sms.component.scss
│   │   │   │   │   ├── sms.component.spec.ts
│   │   │   │   │   └── sms.component.ts
│   │   │   │   ├── sort
│   │   │   │   │   ├── sort.component.html
│   │   │   │   │   ├── sort.component.scss
│   │   │   │   │   ├── sort.component.spec.ts
│   │   │   │   │   └── sort.component.ts
│   │   │   │   ├── speedometer-statistics
│   │   │   │   │   ├── speedometer-statistics.component.html
│   │   │   │   │   ├── speedometer-statistics.component.scss
│   │   │   │   │   ├── speedometer-statistics.component.spec.ts
│   │   │   │   │   └── speedometer-statistics.component.ts
│   │   │   │   ├── stage-representation
│   │   │   │   │   ├── stage-representation.component.html
│   │   │   │   │   ├── stage-representation.component.scss
│   │   │   │   │   ├── stage-representation.component.spec.ts
│   │   │   │   │   └── stage-representation.component.ts
│   │   │   │   ├── statistic-panel
│   │   │   │   │   ├── statistic-panel.component.html
│   │   │   │   │   ├── statistic-panel.component.scss
│   │   │   │   │   ├── statistic-panel.component.spec.ts
│   │   │   │   │   └── statistic-panel.component.ts
│   │   │   │   ├── status-badge
│   │   │   │   │   ├── status-badge.component.html
│   │   │   │   │   ├── status-badge.component.scss
│   │   │   │   │   ├── status-badge.component.spec.ts
│   │   │   │   │   └── status-badge.component.ts
│   │   │   │   ├── status-config
│   │   │   │   │   ├── status-config.component.html
│   │   │   │   │   ├── status-config.component.scss
│   │   │   │   │   ├── status-config.component.spec.ts
│   │   │   │   │   └── status-config.component.ts
│   │   │   │   ├── status-picker
│   │   │   │   │   ├── status-picker.component.html
│   │   │   │   │   ├── status-picker.component.scss
│   │   │   │   │   ├── status-picker.component.spec.ts
│   │   │   │   │   └── status-picker.component.ts
│   │   │   │   ├── submit-ticket-sidebar
│   │   │   │   │   ├── submit-ticket-sidebar.component.html
│   │   │   │   │   ├── submit-ticket-sidebar.component.scss
│   │   │   │   │   ├── submit-ticket-sidebar.component.spec.ts
│   │   │   │   │   └── submit-ticket-sidebar.component.ts
│   │   │   │   ├── summary-card
│   │   │   │   │   ├── summary-card.component.html
│   │   │   │   │   ├── summary-card.component.scss
│   │   │   │   │   ├── summary-card.component.spec.ts
│   │   │   │   │   └── summary-card.component.ts
│   │   │   │   ├── task-tab
│   │   │   │   │   ├── task-tab.component.html
│   │   │   │   │   ├── task-tab.component.scss
│   │   │   │   │   ├── task-tab.component.spec.ts
│   │   │   │   │   └── task-tab.component.ts
│   │   │   │   ├── timeline-graph
│   │   │   │   │   ├── timeline-graph.component.html
│   │   │   │   │   ├── timeline-graph.component.scss
│   │   │   │   │   ├── timeline-graph.component.spec.ts
│   │   │   │   │   └── timeline-graph.component.ts
│   │   │   │   ├── tinymce
│   │   │   │   │   ├── tinymce.component.html
│   │   │   │   │   ├── tinymce.component.scss
│   │   │   │   │   ├── tinymce.component.spec.ts
│   │   │   │   │   └── tinymce.component.ts
│   │   │   │   ├── top-apps-menu
│   │   │   │   │   ├── top-apps-menu.component.html
│   │   │   │   │   ├── top-apps-menu.component.scss
│   │   │   │   │   ├── top-apps-menu.component.spec.ts
│   │   │   │   │   └── top-apps-menu.component.ts
│   │   │   │   ├── tree-crud
│   │   │   │   │   ├── tree-child
│   │   │   │   │   │   ├── tree-child.component.html
│   │   │   │   │   │   ├── tree-child.component.scss
│   │   │   │   │   │   ├── tree-child.component.spec.ts
│   │   │   │   │   │   └── tree-child.component.ts
│   │   │   │   │   ├── tree-crud.component.html
│   │   │   │   │   ├── tree-crud.component.scss
│   │   │   │   │   ├── tree-crud.component.spec.ts
│   │   │   │   │   └── tree-crud.component.ts
│   │   │   │   ├── tree-dropdown-with-icon
│   │   │   │   │   ├── tree-dropdown-with-icon.component.html
│   │   │   │   │   ├── tree-dropdown-with-icon.component.scss
│   │   │   │   │   ├── tree-dropdown-with-icon.component.spec.ts
│   │   │   │   │   └── tree-dropdown-with-icon.component.ts
│   │   │   │   ├── truncate-pipe
│   │   │   │   │   ├── truncate-pipe.component.html
│   │   │   │   │   ├── truncate-pipe.component.scss
│   │   │   │   │   ├── truncate-pipe.component.spec.ts
│   │   │   │   │   └── truncate-pipe.component.ts
│   │   │   │   ├── up-vs-down
│   │   │   │   │   ├── up-vs-down.component.html
│   │   │   │   │   ├── up-vs-down.component.scss
│   │   │   │   │   ├── up-vs-down.component.spec.ts
│   │   │   │   │   └── up-vs-down.component.ts
│   │   │   │   ├── update-custom-drop-down
│   │   │   │   │   ├── update-custom-drop-down.component.html
│   │   │   │   │   ├── update-custom-drop-down.component.scss
│   │   │   │   │   ├── update-custom-drop-down.component.spec.ts
│   │   │   │   │   └── update-custom-drop-down.component.ts
│   │   │   │   ├── user-picker
│   │   │   │   │   ├── user-picker.component.html
│   │   │   │   │   ├── user-picker.component.scss
│   │   │   │   │   ├── user-picker.component.spec.ts
│   │   │   │   │   └── user-picker.component.ts
│   │   │   │   ├── vendor-summary-widget
│   │   │   │   │   ├── vendor-summary-widget.component.html
│   │   │   │   │   ├── vendor-summary-widget.component.scss
│   │   │   │   │   ├── vendor-summary-widget.component.spec.ts
│   │   │   │   │   └── vendor-summary-widget.component.ts
│   │   │   │   ├── widget-text-panel
│   │   │   │   │   ├── widget-text-panel.component.html
│   │   │   │   │   ├── widget-text-panel.component.scss
│   │   │   │   │   ├── widget-text-panel.component.spec.ts
│   │   │   │   │   └── widget-text-panel.component.ts
│   │   │   │   ├── wlc-up-down-panel
│   │   │   │   │   ├── wlc-up-down-panel.component.html
│   │   │   │   │   ├── wlc-up-down-panel.component.scss
│   │   │   │   │   ├── wlc-up-down-panel.component.spec.ts
│   │   │   │   │   └── wlc-up-down-panel.component.ts
│   │   │   │   ├── workflow-conditions
│   │   │   │   │   ├── workflow-conditions.component.html
│   │   │   │   │   ├── workflow-conditions.component.scss
│   │   │   │   │   ├── workflow-conditions.component.spec.ts
│   │   │   │   │   └── workflow-conditions.component.ts
│   │   │   │   └── workflow-skeleton
│   │   │   │       ├── workflow-skeleton.component.html
│   │   │   │       ├── workflow-skeleton.component.scss
│   │   │   │       ├── workflow-skeleton.component.spec.ts
│   │   │   │       └── workflow-skeleton.component.ts
│   │   │   ├── directives
│   │   │   │   ├── component-loader.directive.spec.ts
│   │   │   │   ├── component-loader.directive.ts
│   │   │   │   ├── dns-click.directive.spec.ts
│   │   │   │   ├── dns-click.directive.ts
│   │   │   │   ├── dns-license-handler.directive.spec.ts
│   │   │   │   ├── dns-license-handler.directive.ts
│   │   │   │   ├── enter-submit.directive.spec.ts
│   │   │   │   ├── enter-submit.directive.ts
│   │   │   │   ├── json-text.directive.spec.ts
│   │   │   │   ├── json-text.directive.ts
│   │   │   │   ├── read-more.directive.spec.ts
│   │   │   │   └── read-more.directive.ts
│   │   │   ├── dns.module.ts
│   │   │   ├── pipes
│   │   │   │   ├── date-time.pipe.spec.ts
│   │   │   │   ├── date-time.pipe.ts
│   │   │   │   └── masking-requester-info.pipe.ts
│   │   │   ├── types
│   │   │   │   ├── channel_type.ts
│   │   │   │   ├── column-action.ts
│   │   │   │   ├── column-data.ts
│   │   │   │   ├── emoji_data.ts
│   │   │   │   ├── field_type.ts
│   │   │   │   ├── index.ts
│   │   │   │   ├── modules.ts
│   │   │   │   ├── module_type.ts
│   │   │   │   ├── process_request.ts
│   │   │   │   ├── task_request.ts
│   │   │   │   ├── ticket_card_data.ts
│   │   │   │   ├── ticket_request.ts
│   │   │   │   ├── workflow.type.ts
│   │   │   │   ├── workflow_template_type.ts
│   │   │   │   └── workspace_type.ts
│   │   │   └── validators
│   │   │       ├── compare
│   │   │       │   └── compare.directive.ts
│   │   │       ├── duplicate-label
│   │   │       │   └── duplicate-label-validator.ts
│   │   │       ├── min-max
│   │   │       │   └── min-max-validator.ts
│   │   │       ├── multiemail
│   │   │       │   └── multiemail.directive.ts
│   │   │       ├── multinumber
│   │   │       │   └── multinumber.directive.ts
│   │   │       ├── multiphone
│   │   │       │   └── multiphone.directive.ts
│   │   │       ├── multiselect-validator
│   │   │       │   └── multiselect-validator.directive.ts
│   │   │       ├── quill-validator.directive.ts
│   │   │       ├── range
│   │   │       │   └── range.directive.ts
│   │   │       ├── tree-duplicate-validator
│   │   │       │   └── tree-duplicate-validators.directive.ts
│   │   │       ├── url-validator.ts
│   │   │       └── whitespace
│   │   │           └── whitespace.directive.ts
│   │   ├── guards
│   │   │   ├── auth.guards.ts
│   │   │   └── idParam.guards.ts
│   │   ├── interceptor
│   │   │   ├── dns.http.interceptor.service.spec.ts
│   │   │   └── dns.http.interceptor.service.ts
│   │   ├── layout
│   │   │   ├── components
│   │   │   │   ├── content
│   │   │   │   │   ├── content.component.html
│   │   │   │   │   ├── content.component.ts
│   │   │   │   │   └── content.module.ts
│   │   │   │   ├── content-header
│   │   │   │   │   ├── breadcrumb
│   │   │   │   │   │   ├── breadcrumb.component.html
│   │   │   │   │   │   ├── breadcrumb.component.scss
│   │   │   │   │   │   ├── breadcrumb.component.ts
│   │   │   │   │   │   └── breadcrumb.module.ts
│   │   │   │   │   ├── content-header.component.html
│   │   │   │   │   ├── content-header.component.ts
│   │   │   │   │   └── content-header.module.ts
│   │   │   │   ├── footer
│   │   │   │   │   ├── footer.component.html
│   │   │   │   │   ├── footer.component.ts
│   │   │   │   │   ├── footer.module.ts
│   │   │   │   │   └── scroll-to-top
│   │   │   │   │       ├── scroll-top.component.html
│   │   │   │   │       ├── scroll-top.component.scss
│   │   │   │   │       └── scroll-top.component.ts
│   │   │   │   ├── menu
│   │   │   │   │   ├── admin-menu
│   │   │   │   │   │   ├── admin-menu.component.html
│   │   │   │   │   │   ├── admin-menu.component.scss
│   │   │   │   │   │   ├── admin-menu.component.spec.ts
│   │   │   │   │   │   ├── admin-menu.component.ts
│   │   │   │   │   │   └── admin-menu.module.ts
│   │   │   │   │   ├── horizontal-menu
│   │   │   │   │   │   ├── horizontal-menu.component.html
│   │   │   │   │   │   ├── horizontal-menu.component.scss
│   │   │   │   │   │   ├── horizontal-menu.component.ts
│   │   │   │   │   │   └── horizontal-menu.module.ts
│   │   │   │   │   ├── menu.component.html
│   │   │   │   │   ├── menu.component.scss
│   │   │   │   │   ├── menu.component.ts
│   │   │   │   │   ├── menu.module.ts
│   │   │   │   │   ├── support-menu
│   │   │   │   │   │   ├── support-menu.component.html
│   │   │   │   │   │   ├── support-menu.component.scss
│   │   │   │   │   │   ├── support-menu.component.spec.ts
│   │   │   │   │   │   ├── support-menu.component.ts
│   │   │   │   │   │   └── support-menu.module.ts
│   │   │   │   │   └── vertical-menu
│   │   │   │   │       ├── vertical-menu.component.html
│   │   │   │   │       ├── vertical-menu.component.scss
│   │   │   │   │       ├── vertical-menu.component.ts
│   │   │   │   │       └── vertical-menu.module.ts
│   │   │   │   └── navbar
│   │   │   │       ├── global-search
│   │   │   │       │   ├── global-search.component.html
│   │   │   │       │   ├── global-search.component.scss
│   │   │   │       │   ├── global-search.component.spec.ts
│   │   │   │       │   └── global-search.component.ts
│   │   │   │       ├── navbar-bookmark
│   │   │   │       │   ├── navbar-bookmark.component.html
│   │   │   │       │   └── navbar-bookmark.component.ts
│   │   │   │       ├── navbar-notification
│   │   │   │       │   ├── navbar-notification.component.html
│   │   │   │       │   ├── navbar-notification.component.ts
│   │   │   │       │   └── notifications.service.ts
│   │   │   │       ├── navbar-search
│   │   │   │       │   ├── navbar-search.component.html
│   │   │   │       │   ├── navbar-search.component.scss
│   │   │   │       │   ├── navbar-search.component.ts
│   │   │   │       │   └── search.service.ts
│   │   │   │       ├── navbar.component.html
│   │   │   │       ├── navbar.component.scss
│   │   │   │       ├── navbar.component.ts
│   │   │   │       └── navbar.module.ts
│   │   │   ├── custom-breakpoints.ts
│   │   │   ├── horizontal
│   │   │   │   ├── horizontal-layout.component.html
│   │   │   │   ├── horizontal-layout.component.scss
│   │   │   │   ├── horizontal-layout.component.ts
│   │   │   │   └── horizontal-layout.module.ts
│   │   │   ├── layout.module.ts
│   │   │   └── vertical
│   │   │       ├── vertical-layout.component.html
│   │   │       ├── vertical-layout.component.scss
│   │   │       ├── vertical-layout.component.ts
│   │   │       └── vertical-layout.module.ts
│   │   ├── menu
│   │   │   ├── admin-menu.ts
│   │   │   ├── configuration-menu.ts
│   │   │   ├── i18n
│   │   │   │   ├── ar.json
│   │   │   │   ├── da.json
│   │   │   │   ├── en.json
│   │   │   │   ├── hi.json
│   │   │   │   └── oem.json
│   │   │   ├── infraon-admin-menu.ts
│   │   │   ├── menu.ts
│   │   │   └── support-menu.ts
│   │   ├── notify-banner
│   │   │   ├── notify-banner.component.html
│   │   │   ├── notify-banner.component.scss
│   │   │   ├── notify-banner.component.spec.ts
│   │   │   ├── notify-banner.component.ts
│   │   │   └── notify-banner.module.ts
│   │   ├── pages
│   │   │   ├── components
│   │   │   │   ├── coming-soon
│   │   │   │   │   ├── coming-soon.component.html
│   │   │   │   │   ├── coming-soon.component.scss
│   │   │   │   │   ├── coming-soon.component.spec.ts
│   │   │   │   │   └── coming-soon.component.ts
│   │   │   │   ├── in-active
│   │   │   │   │   ├── in-active.component.html
│   │   │   │   │   ├── in-active.component.scss
│   │   │   │   │   ├── in-active.component.spec.ts
│   │   │   │   │   └── in-active.component.ts
│   │   │   │   ├── privacy-policy
│   │   │   │   │   ├── privacy-policy.component.html
│   │   │   │   │   ├── privacy-policy.component.scss
│   │   │   │   │   ├── privacy-policy.component.spec.ts
│   │   │   │   │   └── privacy-policy.component.ts
│   │   │   │   └── terms
│   │   │   │       ├── terms.component.html
│   │   │   │       ├── terms.component.scss
│   │   │   │       ├── terms.component.spec.ts
│   │   │   │       └── terms.component.ts
│   │   │   ├── pages-routing.module.ts
│   │   │   └── pages.module.ts
│   │   ├── permission
│   │   │   ├── directive.ts
│   │   │   ├── feature-flag-directive.ts
│   │   │   └── service.ts
│   │   ├── schedule
│   │   │   ├── components
│   │   │   │   └── schedule
│   │   │   │       ├── schedule.component.html
│   │   │   │       ├── schedule.component.scss
│   │   │   │       ├── schedule.component.spec.ts
│   │   │   │       └── schedule.component.ts
│   │   │   ├── schedule-routing.module.ts
│   │   │   └── schedule.module.ts
│   │   ├── services
│   │   │   ├── api
│   │   │   │   ├── api.service.spec.ts
│   │   │   │   └── api.service.ts
│   │   │   ├── firebase
│   │   │   │   └── index.ts
│   │   │   ├── jwt
│   │   │   │   └── index.ts
│   │   │   └── wss
│   │   │       ├── wss.service.spec.ts
│   │   │       └── wss.service.ts
│   │   └── utils
│   │       ├── sweet-alerts
│   │       │   └── sweet-alerts.snippetcode.ts
│   │       └── utils.ts
│   ├── ims
│   │   ├── device_credentials
│   │   │   ├── components
│   │   │   │   ├── card-skeleton
│   │   │   │   │   ├── card-skeleton.component.html
│   │   │   │   │   ├── card-skeleton.component.scss
│   │   │   │   │   ├── card-skeleton.component.spec.ts
│   │   │   │   │   └── card-skeleton.component.ts
│   │   │   │   ├── device-credential-card
│   │   │   │   │   ├── device-credential-card.component.html
│   │   │   │   │   ├── device-credential-card.component.scss
│   │   │   │   │   ├── device-credential-card.component.spec.ts
│   │   │   │   │   └── device-credential-card.component.ts
│   │   │   │   ├── login-protocol-sidebar
│   │   │   │   │   ├── login-protocol-sidebar.component.html
│   │   │   │   │   ├── login-protocol-sidebar.component.scss
│   │   │   │   │   └── login-protocol-sidebar.component.ts
│   │   │   │   ├── loginprofile
│   │   │   │   │   ├── loginprofile.component.html
│   │   │   │   │   ├── loginprofile.component.scss
│   │   │   │   │   ├── loginprofile.component.spec.ts
│   │   │   │   │   └── loginprofile.component.ts
│   │   │   │   ├── node-info
│   │   │   │   │   ├── node-info.component.html
│   │   │   │   │   ├── node-info.component.scss
│   │   │   │   │   ├── node-info.component.spec.ts
│   │   │   │   │   └── node-info.component.ts
│   │   │   │   └── skeleton-card
│   │   │   │       ├── skeleton-card.component.html
│   │   │   │       ├── skeleton-card.component.scss
│   │   │   │       ├── skeleton-card.component.spec.ts
│   │   │   │       └── skeleton-card.component.ts
│   │   │   ├── loginprofile-routing.module.ts
│   │   │   ├── loginprofile.module.ts
│   │   │   └── services
│   │   │       ├── loginprofile.service.spec.ts
│   │   │       └── loginprofile.service.ts
│   │   ├── device_template
│   │   │   ├── components
│   │   │   │   ├── add-device-template
│   │   │   │   │   ├── add-device-template.component.html
│   │   │   │   │   ├── add-device-template.component.scss
│   │   │   │   │   ├── add-device-template.component.spec.ts
│   │   │   │   │   └── add-device-template.component.ts
│   │   │   │   ├── add-device-template-mib
│   │   │   │   │   ├── add-device-template-mib.component.html
│   │   │   │   │   ├── add-device-template-mib.component.scss
│   │   │   │   │   └── add-device-template-mib.component.ts
│   │   │   │   ├── device-template-csv-upload
│   │   │   │   │   ├── device-template-csv-upload.component.html
│   │   │   │   │   ├── device-template-csv-upload.component.scss
│   │   │   │   │   ├── device-template-csv-upload.component.spec.ts
│   │   │   │   │   └── device-template-csv-upload.component.ts
│   │   │   │   ├── device-template-grid-view
│   │   │   │   │   ├── device-template-grid-view.component.html
│   │   │   │   │   ├── device-template-grid-view.component.scss
│   │   │   │   │   ├── device-template-grid-view.component.spec.ts
│   │   │   │   │   └── device-template-grid-view.component.ts
│   │   │   │   └── query-device-mib
│   │   │   │       ├── query-device-mib.component.html
│   │   │   │       ├── query-device-mib.component.scss
│   │   │   │       ├── query-device-mib.component.spec.ts
│   │   │   │       └── query-device-mib.component.ts
│   │   │   ├── device-template-routing.module.ts
│   │   │   ├── device-template.module.ts
│   │   │   └── services
│   │   │       ├── device-template.service.spec.ts
│   │   │       └── device-template.service.ts
│   │   ├── diagnosis_tools
│   │   │   ├── components
│   │   │   │   ├── tool
│   │   │   │   │   ├── tool.component.html
│   │   │   │   │   ├── tool.component.scss
│   │   │   │   │   ├── tool.component.spec.ts
│   │   │   │   │   └── tool.component.ts
│   │   │   │   ├── tool-list
│   │   │   │   │   ├── tool-list.component.html
│   │   │   │   │   ├── tool-list.component.scss
│   │   │   │   │   ├── tool-list.component.spec.ts
│   │   │   │   │   └── tool-list.component.ts
│   │   │   │   ├── tool-sidebar
│   │   │   │   │   ├── tool-sidebar.component.html
│   │   │   │   │   ├── tool-sidebar.component.scss
│   │   │   │   │   └── tool-sidebar.component.ts
│   │   │   │   └── toolcard-sidebar
│   │   │   │       ├── toolcard-sidebar.component.html
│   │   │   │       ├── toolcard-sidebar.component.scss
│   │   │   │       ├── toolcard-sidebar.component.spec.ts
│   │   │   │       └── toolcard-sidebar.component.ts
│   │   │   ├── services
│   │   │   │   ├── tool.service.spec.ts
│   │   │   │   └── tool.service.ts
│   │   │   ├── tool-routing.module.ts
│   │   │   └── tool.module.ts
│   │   ├── discovery
│   │   │   ├── components
│   │   │   │   ├── agent
│   │   │   │   │   ├── agent.component.html
│   │   │   │   │   ├── agent.component.scss
│   │   │   │   │   ├── agent.component.spec.ts
│   │   │   │   │   └── agent.component.ts
│   │   │   │   ├── agent-sekeleton
│   │   │   │   │   ├── agent-sekeleton.component.html
│   │   │   │   │   ├── agent-sekeleton.component.scss
│   │   │   │   │   ├── agent-sekeleton.component.spec.ts
│   │   │   │   │   └── agent-sekeleton.component.ts
│   │   │   │   ├── csv-preview
│   │   │   │   │   ├── csv-preview.component.html
│   │   │   │   │   ├── csv-preview.component.scss
│   │   │   │   │   ├── csv-preview.component.spec.ts
│   │   │   │   │   └── csv-preview.component.ts
│   │   │   │   ├── discovery
│   │   │   │   │   ├── discovery.component.html
│   │   │   │   │   ├── discovery.component.scss
│   │   │   │   │   ├── discovery.component.spec.ts
│   │   │   │   │   └── discovery.component.ts
│   │   │   │   ├── discovery-grid
│   │   │   │   │   ├── discovery-grid.component.html
│   │   │   │   │   ├── discovery-grid.component.scss
│   │   │   │   │   ├── discovery-grid.component.spec.ts
│   │   │   │   │   └── discovery-grid.component.ts
│   │   │   │   ├── discovery-info
│   │   │   │   │   ├── discovery-info.component.html
│   │   │   │   │   ├── discovery-info.component.scss
│   │   │   │   │   ├── discovery-info.component.spec.ts
│   │   │   │   │   └── discovery-info.component.ts
│   │   │   │   ├── discovery-job
│   │   │   │   │   ├── discovery-job.component.html
│   │   │   │   │   ├── discovery-job.component.scss
│   │   │   │   │   ├── discovery-job.component.spec.ts
│   │   │   │   │   └── discovery-job.component.ts
│   │   │   │   ├── discovery-list
│   │   │   │   │   ├── discovery-list.component.html
│   │   │   │   │   ├── discovery-list.component.scss
│   │   │   │   │   ├── discovery-list.component.spec.ts
│   │   │   │   │   └── discovery-list.component.ts
│   │   │   │   ├── discoverycard-sidebar
│   │   │   │   │   ├── discoverycard-sidebar.component.html
│   │   │   │   │   ├── discoverycard-sidebar.component.scss
│   │   │   │   │   ├── discoverycard-sidebar.component.spec.ts
│   │   │   │   │   └── discoverycard-sidebar.component.ts
│   │   │   │   ├── schedulediscovery
│   │   │   │   │   ├── schedulediscovery.component.html
│   │   │   │   │   ├── schedulediscovery.component.scss
│   │   │   │   │   ├── schedulediscovery.component.spec.ts
│   │   │   │   │   └── schedulediscovery.component.ts
│   │   │   │   ├── service-monitoring
│   │   │   │   │   ├── service-monitoring.component.html
│   │   │   │   │   ├── service-monitoring.component.scss
│   │   │   │   │   ├── service-monitoring.component.spec.ts
│   │   │   │   │   └── service-monitoring.component.ts
│   │   │   │   └── url-monitoring
│   │   │   │       ├── url-monitoring.component.html
│   │   │   │       ├── url-monitoring.component.scss
│   │   │   │       ├── url-monitoring.component.spec.ts
│   │   │   │       └── url-monitoring.component.ts
│   │   │   ├── config
│   │   │   │   └── discovery-card-config-src.ts
│   │   │   ├── discovery-routing.module.ts
│   │   │   ├── discovery.module.ts
│   │   │   └── services
│   │   │       ├── discovery.service.spec.ts
│   │   │       └── discovery.service.ts
│   │   └── trap_configuration
│   │       ├── components
│   │       │   ├── trap-add
│   │       │   │   ├── trap-add.component.html
│   │       │   │   ├── trap-add.component.scss
│   │       │   │   ├── trap-add.component.spec.ts
│   │       │   │   └── trap-add.component.ts
│   │       │   ├── trap-card
│   │       │   │   ├── trap-card.component.html
│   │       │   │   ├── trap-card.component.scss
│   │       │   │   ├── trap-card.component.spec.ts
│   │       │   │   └── trap-card.component.ts
│   │       │   ├── trap-grid
│   │       │   │   ├── trap-grid.component.html
│   │       │   │   ├── trap-grid.component.scss
│   │       │   │   ├── trap-grid.component.spec.ts
│   │       │   │   └── trap-grid.component.ts
│   │       │   └── trap-msgs
│   │       │       ├── trap-msgs.component.html
│   │       │       ├── trap-msgs.component.scss
│   │       │       ├── trap-msgs.component.spec.ts
│   │       │       └── trap-msgs.component.ts
│   │       ├── services
│   │       │   ├── trap-configuration.service.spec.ts
│   │       │   └── trap-configuration.service.ts
│   │       ├── trap-configuration-routing.module.ts
│   │       └── trap-configuration.module.ts
│   ├── logmanagement
│   │   ├── components
│   │   │   ├── log-cluster-overview
│   │   │   │   ├── log-cluster-overview.component.html
│   │   │   │   ├── log-cluster-overview.component.scss
│   │   │   │   ├── log-cluster-overview.component.spec.ts
│   │   │   │   └── log-cluster-overview.component.ts
│   │   │   ├── log-data-view
│   │   │   │   ├── log-data-view.component.html
│   │   │   │   ├── log-data-view.component.scss
│   │   │   │   ├── log-data-view.component.spec.ts
│   │   │   │   └── log-data-view.component.ts
│   │   │   ├── log-rule
│   │   │   │   ├── log-rule.component.html
│   │   │   │   ├── log-rule.component.scss
│   │   │   │   ├── log-rule.component.spec.ts
│   │   │   │   └── log-rule.component.ts
│   │   │   ├── log-search
│   │   │   │   ├── log-search.component.html
│   │   │   │   ├── log-search.component.scss
│   │   │   │   ├── log-search.component.spec.ts
│   │   │   │   └── log-search.component.ts
│   │   │   ├── log-stream
│   │   │   │   ├── log-stream.component.html
│   │   │   │   ├── log-stream.component.scss
│   │   │   │   ├── log-stream.component.spec.ts
│   │   │   │   └── log-stream.component.ts
│   │   │   └── log-stream-settings
│   │   │       ├── log-stream-settings.component.html
│   │   │       ├── log-stream-settings.component.scss
│   │   │       ├── log-stream-settings.component.spec.ts
│   │   │       └── log-stream-settings.component.ts
│   │   ├── logmanagement-routing.module.ts
│   │   ├── logmanagement.module.ts
│   │   └── services
│   │       ├── logmanagement.service.spec.ts
│   │       └── logmanagement.service.ts
│   ├── marketplace
│   │   ├── components
│   │   │   ├── active-directory
│   │   │   │   ├── active-directory.component.html
│   │   │   │   ├── active-directory.component.scss
│   │   │   │   ├── active-directory.component.spec.ts
│   │   │   │   └── active-directory.component.ts
│   │   │   ├── ad-skeleton
│   │   │   │   ├── ad-skeleton.component.html
│   │   │   │   ├── ad-skeleton.component.scss
│   │   │   │   ├── ad-skeleton.component.spec.ts
│   │   │   │   └── ad-skeleton.component.ts
│   │   │   ├── change-user-sidebar
│   │   │   │   ├── change-user-sidebar.component.html
│   │   │   │   ├── change-user-sidebar.component.scss
│   │   │   │   ├── change-user-sidebar.component.spec.ts
│   │   │   │   └── change-user-sidebar.component.ts
│   │   │   ├── detail-info
│   │   │   │   ├── detail-info.component.html
│   │   │   │   ├── detail-info.component.scss
│   │   │   │   ├── detail-info.component.spec.ts
│   │   │   │   └── detail-info.component.ts
│   │   │   ├── detail-info-image-view
│   │   │   │   ├── detail-info-image-view.component.html
│   │   │   │   ├── detail-info-image-view.component.scss
│   │   │   │   ├── detail-info-image-view.component.spec.ts
│   │   │   │   └── detail-info-image-view.component.ts
│   │   │   ├── edit-configuration
│   │   │   │   ├── edit-configuration.component.html
│   │   │   │   ├── edit-configuration.component.scss
│   │   │   │   ├── edit-configuration.component.spec.ts
│   │   │   │   └── edit-configuration.component.ts
│   │   │   ├── google-workspace-config
│   │   │   │   ├── google-workspace-config.component.html
│   │   │   │   ├── google-workspace-config.component.scss
│   │   │   │   ├── google-workspace-config.component.spec.ts
│   │   │   │   └── google-workspace-config.component.ts
│   │   │   ├── jamf-configuration
│   │   │   │   ├── jamf-configuration.component.html
│   │   │   │   ├── jamf-configuration.component.scss
│   │   │   │   ├── jamf-configuration.component.spec.ts
│   │   │   │   └── jamf-configuration.component.ts
│   │   │   ├── jira-config
│   │   │   │   ├── jira-config.component.html
│   │   │   │   ├── jira-config.component.scss
│   │   │   │   ├── jira-config.component.spec.ts
│   │   │   │   └── jira-config.component.ts
│   │   │   ├── ldap-config
│   │   │   │   ├── ldap-config.component.html
│   │   │   │   ├── ldap-config.component.scss
│   │   │   │   ├── ldap-config.component.spec.ts
│   │   │   │   └── ldap-config.component.ts
│   │   │   ├── market-place
│   │   │   │   ├── market-place.component.html
│   │   │   │   ├── market-place.component.scss
│   │   │   │   ├── market-place.component.spec.ts
│   │   │   │   └── market-place.component.ts
│   │   │   ├── product-detail
│   │   │   │   ├── product-detail.component.html
│   │   │   │   ├── product-detail.component.scss
│   │   │   │   ├── product-detail.component.spec.ts
│   │   │   │   └── product-detail.component.ts
│   │   │   ├── ring-central-config
│   │   │   │   ├── ring-central-config.component.html
│   │   │   │   ├── ring-central-config.component.scss
│   │   │   │   ├── ring-central-config.component.spec.ts
│   │   │   │   └── ring-central-config.component.ts
│   │   │   ├── servicenow-config
│   │   │   │   ├── servicenow-config.component.html
│   │   │   │   ├── servicenow-config.component.scss
│   │   │   │   ├── servicenow-config.component.spec.ts
│   │   │   │   └── servicenow-config.component.ts
│   │   │   ├── teams-edit-configuration
│   │   │   │   ├── teams-edit-configuration.component.html
│   │   │   │   ├── teams-edit-configuration.component.scss
│   │   │   │   ├── teams-edit-configuration.component.spec.ts
│   │   │   │   └── teams-edit-configuration.component.ts
│   │   │   └── whatsapp-message-templates
│   │   │       ├── whatsapp-message-templates.component.html
│   │   │       ├── whatsapp-message-templates.component.scss
│   │   │       ├── whatsapp-message-templates.component.spec.ts
│   │   │       └── whatsapp-message-templates.component.ts
│   │   ├── google-configuration
│   │   │   ├── google-signin.component.html
│   │   │   ├── google-signin.component.scss
│   │   │   ├── google-signin.component.spec.ts
│   │   │   └── google-signin.component.ts
│   │   ├── marketplace-routing.module.ts
│   │   ├── marketplace.module.ts
│   │   ├── models
│   │   │   ├── app.ts
│   │   │   └── index.ts
│   │   └── services
│   │       ├── marketplace-api.service.spec.ts
│   │       ├── marketplace-api.service.ts
│   │       ├── marketplace.service.spec.ts
│   │       └── marketplace.service.ts
│   ├── nccm
│   │   ├── base-scheduler
│   │   │   ├── baseline-scheduler-routing.module.ts
│   │   │   ├── baseline-scheduler.module.ts
│   │   │   ├── components
│   │   │   │   └── baseline-scheduler
│   │   │   │       ├── add-baseline-configuration
│   │   │   │       │   ├── add-baseline-configuration.component.html
│   │   │   │       │   ├── add-baseline-configuration.component.scss
│   │   │   │       │   ├── add-baseline-configuration.component.spec.ts
│   │   │   │       │   └── add-baseline-configuration.component.ts
│   │   │   │       ├── add-set-baseline
│   │   │   │       │   ├── add-set-baseline.component.html
│   │   │   │       │   ├── add-set-baseline.component.scss
│   │   │   │       │   ├── add-set-baseline.component.spec.ts
│   │   │   │       │   └── add-set-baseline.component.ts
│   │   │   │       ├── baseline-scheduler.component.html
│   │   │   │       ├── baseline-scheduler.component.scss
│   │   │   │       ├── baseline-scheduler.component.spec.ts
│   │   │   │       └── baseline-scheduler.component.ts
│   │   │   └── services
│   │   │       ├── base-scheduler.service.spec.ts
│   │   │       └── base-scheduler.service.ts
│   │   ├── calendar
│   │   │   ├── calendar-routing.module.ts
│   │   │   ├── calendar.module.ts
│   │   │   ├── components
│   │   │   │   ├── calenadr-view
│   │   │   │   │   ├── calenadr-view.component.html
│   │   │   │   │   ├── calenadr-view.component.scss
│   │   │   │   │   ├── calenadr-view.component.spec.ts
│   │   │   │   │   └── calenadr-view.component.ts
│   │   │   │   └── calendar-view-side-bar
│   │   │   │       ├── calendar-view-side-bar.component.html
│   │   │   │       ├── calendar-view-side-bar.component.scss
│   │   │   │       ├── calendar-view-side-bar.component.spec.ts
│   │   │   │       └── calendar-view-side-bar.component.ts
│   │   │   └── services
│   │   │       ├── calendar.service.spec.ts
│   │   │       └── calendar.service.ts
│   │   ├── cli-job
│   │   │   ├── cli-job-routing.module.ts
│   │   │   ├── cli-job.module.ts
│   │   │   ├── components
│   │   │   │   ├── cli-job
│   │   │   │   │   ├── cli-job.component.html
│   │   │   │   │   ├── cli-job.component.scss
│   │   │   │   │   ├── cli-job.component.spec.ts
│   │   │   │   │   └── cli-job.component.ts
│   │   │   │   ├── cli-session-audit-view
│   │   │   │   │   ├── cli-session-audit-view.component.html
│   │   │   │   │   ├── cli-session-audit-view.component.scss
│   │   │   │   │   ├── cli-session-audit-view.component.spec.ts
│   │   │   │   │   └── cli-session-audit-view.component.ts
│   │   │   │   └── view-cli-details
│   │   │   │       ├── view-cli-details.component.html
│   │   │   │       ├── view-cli-details.component.scss
│   │   │   │       ├── view-cli-details.component.spec.ts
│   │   │   │       └── view-cli-details.component.ts
│   │   │   └── services
│   │   │       ├── cli-job.service.spec.ts
│   │   │       └── cli-job.service.ts
│   │   ├── configuration-comparison
│   │   │   ├── components
│   │   │   │   └── configuration-compare
│   │   │   │       ├── configuration-compare.component.html
│   │   │   │       ├── configuration-compare.component.scss
│   │   │   │       ├── configuration-compare.component.spec.ts
│   │   │   │       └── configuration-compare.component.ts
│   │   │   ├── configuration-comparison-routing.module.ts
│   │   │   ├── configuration-comparison.module.ts
│   │   │   └── services
│   │   │       ├── configuration-comparison.service.spec.ts
│   │   │       └── configuration-comparison.service.ts
│   │   ├── configuration-file-comparison
│   │   │   ├── components
│   │   │   │   └── configuration-file-comparison
│   │   │   │       ├── configuration-file-comparison.component.html
│   │   │   │       ├── configuration-file-comparison.component.scss
│   │   │   │       ├── configuration-file-comparison.component.spec.ts
│   │   │   │       └── configuration-file-comparison.component.ts
│   │   │   ├── configuration-file-comparison-routing.module.ts
│   │   │   ├── configuration-file-comparison.module.ts
│   │   │   └── services
│   │   │       ├── configuration-file-comparison.service.spec.ts
│   │   │       └── configuration-file-comparison.service.ts
│   │   ├── configuration-profile
│   │   │   ├── components
│   │   │   │   ├── config-code-editor
│   │   │   │   │   ├── config-code-editor.component.html
│   │   │   │   │   ├── config-code-editor.component.scss
│   │   │   │   │   ├── config-code-editor.component.spec.ts
│   │   │   │   │   └── config-code-editor.component.ts
│   │   │   │   ├── configuration-code-sidebar
│   │   │   │   │   ├── configuration-code-sidebar.component.html
│   │   │   │   │   ├── configuration-code-sidebar.component.scss
│   │   │   │   │   ├── configuration-code-sidebar.component.spec.ts
│   │   │   │   │   └── configuration-code-sidebar.component.ts
│   │   │   │   ├── configuration-profile-grid
│   │   │   │   │   ├── configuration-profile-grid.component.html
│   │   │   │   │   ├── configuration-profile-grid.component.scss
│   │   │   │   │   ├── configuration-profile-grid.component.spec.ts
│   │   │   │   │   └── configuration-profile-grid.component.ts
│   │   │   │   ├── configuration-view
│   │   │   │   │   ├── configuration-view.component.html
│   │   │   │   │   ├── configuration-view.component.scss
│   │   │   │   │   ├── configuration-view.component.spec.ts
│   │   │   │   │   └── configuration-view.component.ts
│   │   │   │   ├── create-configuration-profile-form
│   │   │   │   │   ├── create-configuration-profile-form.component.html
│   │   │   │   │   ├── create-configuration-profile-form.component.scss
│   │   │   │   │   ├── create-configuration-profile-form.component.spec.ts
│   │   │   │   │   └── create-configuration-profile-form.component.ts
│   │   │   │   ├── import-configuration-profile
│   │   │   │   │   ├── import-configuration-profile.component.html
│   │   │   │   │   ├── import-configuration-profile.component.scss
│   │   │   │   │   ├── import-configuration-profile.component.spec.ts
│   │   │   │   │   └── import-configuration-profile.component.ts
│   │   │   │   └── using-profile
│   │   │   │       ├── using-profile.component.html
│   │   │   │       ├── using-profile.component.scss
│   │   │   │       ├── using-profile.component.spec.ts
│   │   │   │       └── using-profile.component.ts
│   │   │   ├── configuration-profile-routing.module.ts
│   │   │   ├── configuration-profile.module.ts
│   │   │   └── services
│   │   │       ├── configuration-profile.service.spec.ts
│   │   │       └── configuration-profile.service.ts
│   │   ├── configuration-search
│   │   │   ├── components
│   │   │   │   └── configuration-search-grid
│   │   │   │       ├── configuration-search-grid.component.html
│   │   │   │       ├── configuration-search-grid.component.scss
│   │   │   │       ├── configuration-search-grid.component.spec.ts
│   │   │   │       └── configuration-search-grid.component.ts
│   │   │   ├── configuration-search-routing.module.ts
│   │   │   ├── configuration-search.module.ts
│   │   │   └── services
│   │   │       ├── configuration-search.service.spec.ts
│   │   │       └── configuration-search.service.ts
│   │   ├── configuration-template
│   │   │   ├── components
│   │   │   │   ├── configration-template-grid-view
│   │   │   │   │   ├── configration-template-grid-view.component.html
│   │   │   │   │   ├── configration-template-grid-view.component.scss
│   │   │   │   │   ├── configration-template-grid-view.component.spec.ts
│   │   │   │   │   └── configration-template-grid-view.component.ts
│   │   │   │   ├── configuration-template-csv-upload
│   │   │   │   │   ├── configuration-template-csv-upload.component.html
│   │   │   │   │   ├── configuration-template-csv-upload.component.scss
│   │   │   │   │   ├── configuration-template-csv-upload.component.spec.ts
│   │   │   │   │   └── configuration-template-csv-upload.component.ts
│   │   │   │   ├── configuration-template-info
│   │   │   │   │   ├── configuration-template-info.component.html
│   │   │   │   │   ├── configuration-template-info.component.scss
│   │   │   │   │   ├── configuration-template-info.component.spec.ts
│   │   │   │   │   └── configuration-template-info.component.ts
│   │   │   │   └── create-configuration-template
│   │   │   │       ├── create-configuration-template.component.html
│   │   │   │       ├── create-configuration-template.component.scss
│   │   │   │       ├── create-configuration-template.component.spec.ts
│   │   │   │       └── create-configuration-template.component.ts
│   │   │   ├── configuration-template-routing.module.ts
│   │   │   ├── configuration-template.module.ts
│   │   │   └── services
│   │   │       ├── configuration-template.service.spec.ts
│   │   │       └── configuration-template.service.ts
│   │   ├── download-job
│   │   │   ├── components
│   │   │   │   ├── add-download-jobs
│   │   │   │   │   ├── add-download-jobs.component.html
│   │   │   │   │   ├── add-download-jobs.component.scss
│   │   │   │   │   ├── add-download-jobs.component.spec.ts
│   │   │   │   │   └── add-download-jobs.component.ts
│   │   │   │   ├── bulk-edit-sidebar
│   │   │   │   │   ├── bulk-edit-sidebar.component.html
│   │   │   │   │   ├── bulk-edit-sidebar.component.scss
│   │   │   │   │   ├── bulk-edit-sidebar.component.spec.ts
│   │   │   │   │   └── bulk-edit-sidebar.component.ts
│   │   │   │   ├── configuration-comparison-details
│   │   │   │   │   ├── configuration-comparison-details.component.html
│   │   │   │   │   ├── configuration-comparison-details.component.scss
│   │   │   │   │   ├── configuration-comparison-details.component.spec.ts
│   │   │   │   │   └── configuration-comparison-details.component.ts
│   │   │   │   ├── configuration-details
│   │   │   │   │   ├── configuration-details.component.html
│   │   │   │   │   ├── configuration-details.component.scss
│   │   │   │   │   ├── configuration-details.component.spec.ts
│   │   │   │   │   └── configuration-details.component.ts
│   │   │   │   ├── configuration-details-view
│   │   │   │   │   ├── configuration-details-view.component.html
│   │   │   │   │   ├── configuration-details-view.component.scss
│   │   │   │   │   ├── configuration-details-view.component.spec.ts
│   │   │   │   │   └── configuration-details-view.component.ts
│   │   │   │   ├── csv-download-job-edit
│   │   │   │   │   ├── csv-download-job-edit.component.html
│   │   │   │   │   ├── csv-download-job-edit.component.scss
│   │   │   │   │   ├── csv-download-job-edit.component.spec.ts
│   │   │   │   │   └── csv-download-job-edit.component.ts
│   │   │   │   ├── current-download-configuration
│   │   │   │   │   ├── current-download-configuration.component.html
│   │   │   │   │   ├── current-download-configuration.component.scss
│   │   │   │   │   ├── current-download-configuration.component.spec.ts
│   │   │   │   │   └── current-download-configuration.component.ts
│   │   │   │   ├── download-audit-grid
│   │   │   │   │   ├── download-audit-grid.component.html
│   │   │   │   │   ├── download-audit-grid.component.scss
│   │   │   │   │   ├── download-audit-grid.component.spec.ts
│   │   │   │   │   └── download-audit-grid.component.ts
│   │   │   │   ├── download-job
│   │   │   │   │   ├── download-job.component.html
│   │   │   │   │   ├── download-job.component.scss
│   │   │   │   │   ├── download-job.component.spec.ts
│   │   │   │   │   └── download-job.component.ts
│   │   │   │   ├── download-job-grid
│   │   │   │   │   ├── download-job-grid.component.html
│   │   │   │   │   ├── download-job-grid.component.scss
│   │   │   │   │   ├── download-job-grid.component.spec.ts
│   │   │   │   │   └── download-job-grid.component.ts
│   │   │   │   ├── download-job-smart-grid
│   │   │   │   │   ├── download-job-smart-grid.component.html
│   │   │   │   │   ├── download-job-smart-grid.component.scss
│   │   │   │   │   ├── download-job-smart-grid.component.spec.ts
│   │   │   │   │   └── download-job-smart-grid.component.ts
│   │   │   │   ├── download-results-grid
│   │   │   │   │   ├── download-results-grid.component.html
│   │   │   │   │   ├── download-results-grid.component.scss
│   │   │   │   │   ├── download-results-grid.component.spec.ts
│   │   │   │   │   └── download-results-grid.component.ts
│   │   │   │   ├── import-download-jobs
│   │   │   │   │   ├── import-download-jobs.component.html
│   │   │   │   │   ├── import-download-jobs.component.scss
│   │   │   │   │   ├── import-download-jobs.component.spec.ts
│   │   │   │   │   └── import-download-jobs.component.ts
│   │   │   │   └── status-download-job
│   │   │   │       ├── status-download-job.component.html
│   │   │   │       ├── status-download-job.component.scss
│   │   │   │       ├── status-download-job.component.spec.ts
│   │   │   │       └── status-download-job.component.ts
│   │   │   ├── download-job-routing.module.ts
│   │   │   ├── download-job.module.ts
│   │   │   └── services
│   │   │       ├── download-job.service.spec.ts
│   │   │       └── download-job.service.ts
│   │   ├── generate-md5
│   │   │   ├── components
│   │   │   │   └── generate-md5-key
│   │   │   │       ├── generate-md5-key.component.html
│   │   │   │       ├── generate-md5-key.component.scss
│   │   │   │       ├── generate-md5-key.component.spec.ts
│   │   │   │       └── generate-md5-key.component.ts
│   │   │   ├── generate-md5-routing.module.ts
│   │   │   ├── generate-md5.module.ts
│   │   │   └── services
│   │   │       ├── generate-md5-key.service.spec.ts
│   │   │       └── generate-md5-key.service.ts
│   │   ├── global-parameters
│   │   │   ├── components
│   │   │   │   ├── add-global-parameters
│   │   │   │   │   ├── add-global-parameters.component.html
│   │   │   │   │   ├── add-global-parameters.component.scss
│   │   │   │   │   ├── add-global-parameters.component.spec.ts
│   │   │   │   │   └── add-global-parameters.component.ts
│   │   │   │   ├── global-parameters-grid
│   │   │   │   │   ├── global-parameters-grid.component.html
│   │   │   │   │   ├── global-parameters-grid.component.scss
│   │   │   │   │   ├── global-parameters-grid.component.spec.ts
│   │   │   │   │   └── global-parameters-grid.component.ts
│   │   │   │   └── import-global-parameters
│   │   │   │       ├── import-global-parameters.component.html
│   │   │   │       ├── import-global-parameters.component.scss
│   │   │   │       ├── import-global-parameters.component.spec.ts
│   │   │   │       └── import-global-parameters.component.ts
│   │   │   ├── global-parameters-routing.module.ts
│   │   │   ├── global-parameters.module.ts
│   │   │   └── services
│   │   │       ├── global-parameters.service.spec.ts
│   │   │       └── global-parameters.service.ts
│   │   ├── jobs-account-audit
│   │   │   ├── components
│   │   │   │   └── jobs-account-audit-grid
│   │   │   │       ├── jobs-account-audit-grid.component.html
│   │   │   │       ├── jobs-account-audit-grid.component.scss
│   │   │   │       ├── jobs-account-audit-grid.component.spec.ts
│   │   │   │       └── jobs-account-audit-grid.component.ts
│   │   │   ├── jobs-account-audit-routing.module.ts
│   │   │   ├── jobs-account-audit.module.ts
│   │   │   └── services
│   │   │       ├── jobs-account-audit.service.spec.ts
│   │   │       └── jobs-account-audit.service.ts
│   │   ├── network-configuration
│   │   │   ├── components
│   │   │   │   ├── network
│   │   │   │   │   ├── network.component.html
│   │   │   │   │   ├── network.component.scss
│   │   │   │   │   ├── network.component.spec.ts
│   │   │   │   │   └── network.component.ts
│   │   │   │   ├── network-list
│   │   │   │   │   ├── network-list.component.html
│   │   │   │   │   ├── network-list.component.scss
│   │   │   │   │   ├── network-list.component.spec.ts
│   │   │   │   │   └── network-list.component.ts
│   │   │   │   └── networkcard-sidebar
│   │   │   │       ├── networkcard-sidebar.component.html
│   │   │   │       ├── networkcard-sidebar.component.scss
│   │   │   │       ├── networkcard-sidebar.component.spec.ts
│   │   │   │       └── networkcard-sidebar.component.ts
│   │   │   ├── network-routing.module.ts
│   │   │   ├── network.module.ts
│   │   │   └── services
│   │   │       ├── network.service.spec.ts
│   │   │       └── network.service.ts
│   │   ├── os-image
│   │   │   ├── components
│   │   │   │   ├── add-os-image
│   │   │   │   │   ├── add-os-image.component.html
│   │   │   │   │   ├── add-os-image.component.scss
│   │   │   │   │   ├── add-os-image.component.spec.ts
│   │   │   │   │   └── add-os-image.component.ts
│   │   │   │   ├── download-os-job-audits
│   │   │   │   │   ├── download-os-job-audits.component.html
│   │   │   │   │   ├── download-os-job-audits.component.scss
│   │   │   │   │   ├── download-os-job-audits.component.spec.ts
│   │   │   │   │   └── download-os-job-audits.component.ts
│   │   │   │   ├── os-image
│   │   │   │   │   ├── os-image.component.html
│   │   │   │   │   ├── os-image.component.scss
│   │   │   │   │   ├── os-image.component.spec.ts
│   │   │   │   │   └── os-image.component.ts
│   │   │   │   ├── os-image-download-status
│   │   │   │   │   ├── os-image-download-status.component.html
│   │   │   │   │   ├── os-image-download-status.component.scss
│   │   │   │   │   ├── os-image-download-status.component.spec.ts
│   │   │   │   │   └── os-image-download-status.component.ts
│   │   │   │   └── os-version-view
│   │   │   │       ├── os-version-view.component.html
│   │   │   │       ├── os-version-view.component.scss
│   │   │   │       ├── os-version-view.component.spec.ts
│   │   │   │       └── os-version-view.component.ts
│   │   │   ├── os-image-routing.module.ts
│   │   │   ├── os-image.module.ts
│   │   │   └── services
│   │   │       ├── os-image.service.spec.ts
│   │   │       └── os-image.service.ts
│   │   ├── os-image-schedular
│   │   │   ├── components
│   │   │   │   ├── add-os-image-schedule
│   │   │   │   │   ├── add-os-image-schedule.component.html
│   │   │   │   │   ├── add-os-image-schedule.component.scss
│   │   │   │   │   ├── add-os-image-schedule.component.spec.ts
│   │   │   │   │   └── add-os-image-schedule.component.ts
│   │   │   │   └── os-image-schedular-gird
│   │   │   │       ├── os-image-schedular-gird.component.html
│   │   │   │       ├── os-image-schedular-gird.component.scss
│   │   │   │       ├── os-image-schedular-gird.component.spec.ts
│   │   │   │       └── os-image-schedular-gird.component.ts
│   │   │   ├── os-image-schedular-routing.module.ts
│   │   │   ├── os-image-schedular.module.ts
│   │   │   └── services
│   │   │       ├── os-image-schedular.service.spec.ts
│   │   │       └── os-image-schedular.service.ts
│   │   └── sysobjectid
│   │       ├── components
│   │       │   ├── add-sysobjectid
│   │       │   │   ├── add-sysobjectid.component.html
│   │       │   │   ├── add-sysobjectid.component.scss
│   │       │   │   ├── add-sysobjectid.component.spec.ts
│   │       │   │   └── add-sysobjectid.component.ts
│   │       │   ├── sysobjectid-csv-upload
│   │       │   │   ├── sysobjectid-csv-upload.component.html
│   │       │   │   ├── sysobjectid-csv-upload.component.scss
│   │       │   │   ├── sysobjectid-csv-upload.component.spec.ts
│   │       │   │   └── sysobjectid-csv-upload.component.ts
│   │       │   └── sysobjectid-grid-view
│   │       │       ├── sysobjectid-grid-view.component.html
│   │       │       ├── sysobjectid-grid-view.component.scss
│   │       │       ├── sysobjectid-grid-view.component.spec.ts
│   │       │       └── sysobjectid-grid-view.component.ts
│   │       ├── services
│   │       │   ├── sysobjectid.service.spec.ts
│   │       │   └── sysobjectid.service.ts
│   │       ├── sysobjectid-routing.module.ts
│   │       └── sysobjectid.module.ts
│   ├── new-tag
│   │   ├── components
│   │   │   ├── new-tag
│   │   │   │   ├── new-tag.component.html
│   │   │   │   ├── new-tag.component.scss
│   │   │   │   ├── new-tag.component.spec.ts
│   │   │   │   └── new-tag.component.ts
│   │   │   ├── new-tag-card
│   │   │   │   ├── new-tag-card.component.html
│   │   │   │   ├── new-tag-card.component.scss
│   │   │   │   ├── new-tag-card.component.spec.ts
│   │   │   │   └── new-tag-card.component.ts
│   │   │   └── new-tag-grid
│   │   │       ├── new-tag-grid.component.html
│   │   │       ├── new-tag-grid.component.scss
│   │   │       ├── new-tag-grid.component.spec.ts
│   │   │       └── new-tag-grid.component.ts
│   │   ├── new-tag-routing.module.ts
│   │   ├── new-tag.module.ts
│   │   └── service
│   │       ├── tag-service.service.spec.ts
│   │       └── tag-service.service.ts
│   ├── self-service-portal
│   │   ├── components
│   │   │   ├── asset-details
│   │   │   │   ├── asset-details.component.html
│   │   │   │   ├── asset-details.component.scss
│   │   │   │   ├── asset-details.component.spec.ts
│   │   │   │   └── asset-details.component.ts
│   │   │   ├── assets
│   │   │   │   ├── assets.component.html
│   │   │   │   ├── assets.component.scss
│   │   │   │   ├── assets.component.spec.ts
│   │   │   │   └── assets.component.ts
│   │   │   ├── change
│   │   │   │   ├── change.component.html
│   │   │   │   ├── change.component.scss
│   │   │   │   ├── change.component.spec.ts
│   │   │   │   └── change.component.ts
│   │   │   ├── change-details
│   │   │   │   ├── change-details.component.html
│   │   │   │   ├── change-details.component.scss
│   │   │   │   ├── change-details.component.spec.ts
│   │   │   │   └── change-details.component.ts
│   │   │   ├── kb-detail
│   │   │   │   ├── kb-detail.component.html
│   │   │   │   ├── kb-detail.component.scss
│   │   │   │   ├── kb-detail.component.spec.ts
│   │   │   │   └── kb-detail.component.ts
│   │   │   ├── kb-list
│   │   │   │   ├── kb-list.component.html
│   │   │   │   ├── kb-list.component.scss
│   │   │   │   ├── kb-list.component.spec.ts
│   │   │   │   └── kb-list.component.ts
│   │   │   ├── kb-ratings
│   │   │   │   ├── kb-ratings.component.html
│   │   │   │   ├── kb-ratings.component.scss
│   │   │   │   ├── kb-ratings.component.spec.ts
│   │   │   │   └── kb-ratings.component.ts
│   │   │   ├── kb-views
│   │   │   │   ├── kb-views.component.html
│   │   │   │   ├── kb-views.component.scss
│   │   │   │   ├── kb-views.component.spec.ts
│   │   │   │   └── kb-views.component.ts
│   │   │   ├── request-details
│   │   │   │   ├── request-details.component.html
│   │   │   │   ├── request-details.component.scss
│   │   │   │   ├── request-details.component.spec.ts
│   │   │   │   └── request-details.component.ts
│   │   │   ├── requests
│   │   │   │   ├── requests.component.html
│   │   │   │   ├── requests.component.scss
│   │   │   │   ├── requests.component.spec.ts
│   │   │   │   └── requests.component.ts
│   │   │   ├── self-service
│   │   │   │   ├── self-service.component.html
│   │   │   │   ├── self-service.component.scss
│   │   │   │   ├── self-service.component.spec.ts
│   │   │   │   └── self-service.component.ts
│   │   │   ├── ticket-details
│   │   │   │   ├── ticket-details.component.html
│   │   │   │   ├── ticket-details.component.scss
│   │   │   │   ├── ticket-details.component.spec.ts
│   │   │   │   └── ticket-details.component.ts
│   │   │   └── tickets
│   │   │       ├── tickets.component.html
│   │   │       ├── tickets.component.scss
│   │   │       ├── tickets.component.spec.ts
│   │   │       └── tickets.component.ts
│   │   ├── self-service-portal-routing.module.ts
│   │   ├── self-service-portal.module.ts
│   │   └── services
│   │       ├── asset.service.ts
│   │       ├── self-service-portal.service.spec.ts
│   │       └── self-service-portal.service.ts
│   ├── servicedesk
│   │   ├── change-management
│   │   │   ├── change-management-routing.module.ts
│   │   │   ├── change-management.module.ts
│   │   │   ├── component
│   │   │   │   ├── add-change
│   │   │   │   │   ├── add-change.component.html
│   │   │   │   │   ├── add-change.component.scss
│   │   │   │   │   ├── add-change.component.spec.ts
│   │   │   │   │   └── add-change.component.ts
│   │   │   │   ├── analysis-submition
│   │   │   │   │   ├── analysis-submition.component.html
│   │   │   │   │   ├── analysis-submition.component.scss
│   │   │   │   │   ├── analysis-submition.component.spec.ts
│   │   │   │   │   └── analysis-submition.component.ts
│   │   │   │   ├── calendar
│   │   │   │   │   ├── calendar.component.html
│   │   │   │   │   ├── calendar.component.scss
│   │   │   │   │   └── calendar.component.ts
│   │   │   │   ├── calendar-event-sidebar
│   │   │   │   │   ├── calendar-event-sidebar.component.html
│   │   │   │   │   └── calendar-event-sidebar.component.ts
│   │   │   │   ├── calendar-main-sidebar
│   │   │   │   │   ├── calendar-main-sidebar.component.html
│   │   │   │   │   └── calendar-main-sidebar.component.ts
│   │   │   │   ├── change-approval
│   │   │   │   │   ├── change-approval.component.html
│   │   │   │   │   ├── change-approval.component.scss
│   │   │   │   │   ├── change-approval.component.spec.ts
│   │   │   │   │   └── change-approval.component.ts
│   │   │   │   ├── change-assignee
│   │   │   │   │   ├── change-assignee.component.html
│   │   │   │   │   ├── change-assignee.component.scss
│   │   │   │   │   ├── change-assignee.component.spec.ts
│   │   │   │   │   └── change-assignee.component.ts
│   │   │   │   ├── change-attachment
│   │   │   │   │   ├── change-attachment.component.html
│   │   │   │   │   ├── change-attachment.component.scss
│   │   │   │   │   ├── change-attachment.component.spec.ts
│   │   │   │   │   └── change-attachment.component.ts
│   │   │   │   ├── change-close
│   │   │   │   │   ├── change-close.component.html
│   │   │   │   │   ├── change-close.component.scss
│   │   │   │   │   ├── change-close.component.spec.ts
│   │   │   │   │   └── change-close.component.ts
│   │   │   │   ├── change-comment
│   │   │   │   │   ├── change-comment.component.html
│   │   │   │   │   ├── change-comment.component.scss
│   │   │   │   │   ├── change-comment.component.spec.ts
│   │   │   │   │   └── change-comment.component.ts
│   │   │   │   ├── change-edit-sidebar
│   │   │   │   │   ├── change-edit-sidebar.component.html
│   │   │   │   │   ├── change-edit-sidebar.component.scss
│   │   │   │   │   ├── change-edit-sidebar.component.spec.ts
│   │   │   │   │   └── change-edit-sidebar.component.ts
│   │   │   │   ├── change-history
│   │   │   │   │   ├── change-history.component.html
│   │   │   │   │   ├── change-history.component.scss
│   │   │   │   │   ├── change-history.component.spec.ts
│   │   │   │   │   └── change-history.component.ts
│   │   │   │   ├── change-impact
│   │   │   │   │   ├── change-impact.component.html
│   │   │   │   │   ├── change-impact.component.scss
│   │   │   │   │   ├── change-impact.component.spec.ts
│   │   │   │   │   └── change-impact.component.ts
│   │   │   │   ├── change-interaction
│   │   │   │   │   ├── change-interaction.component.html
│   │   │   │   │   ├── change-interaction.component.scss
│   │   │   │   │   ├── change-interaction.component.spec.ts
│   │   │   │   │   └── change-interaction.component.ts
│   │   │   │   ├── change-management-grid
│   │   │   │   │   ├── change-management-grid.component.html
│   │   │   │   │   ├── change-management-grid.component.scss
│   │   │   │   │   ├── change-management-grid.component.spec.ts
│   │   │   │   │   └── change-management-grid.component.ts
│   │   │   │   ├── change-quick-edit
│   │   │   │   │   ├── change-quick-edit.component.html
│   │   │   │   │   ├── change-quick-edit.component.scss
│   │   │   │   │   ├── change-quick-edit.component.spec.ts
│   │   │   │   │   └── change-quick-edit.component.ts
│   │   │   │   ├── change-risk
│   │   │   │   │   ├── change-risk.component.html
│   │   │   │   │   ├── change-risk.component.scss
│   │   │   │   │   ├── change-risk.component.spec.ts
│   │   │   │   │   └── change-risk.component.ts
│   │   │   │   ├── change-risk-list
│   │   │   │   │   ├── change-risk-list.html
│   │   │   │   │   ├── change-risk-list.scss
│   │   │   │   │   ├── change-risk-list.spec.ts
│   │   │   │   │   └── change-risk-list.ts
│   │   │   │   ├── change-skeleton
│   │   │   │   │   ├── change-skeleton.component.html
│   │   │   │   │   ├── change-skeleton.component.scss
│   │   │   │   │   ├── change-skeleton.component.spec.ts
│   │   │   │   │   └── change-skeleton.component.ts
│   │   │   │   ├── change-sla-info
│   │   │   │   │   ├── change-sla-info.component.html
│   │   │   │   │   ├── change-sla-info.component.scss
│   │   │   │   │   ├── change-sla-info.component.spec.ts
│   │   │   │   │   └── change-sla-info.component.ts
│   │   │   │   ├── change-task-list
│   │   │   │   │   ├── change-task-list.html
│   │   │   │   │   ├── change-task-list.scss
│   │   │   │   │   ├── change-task-list.spec.ts
│   │   │   │   │   └── change-task-list.ts
│   │   │   │   ├── change-to-incident
│   │   │   │   │   ├── change-to-incident.component.html
│   │   │   │   │   ├── change-to-incident.component.scss
│   │   │   │   │   ├── change-to-incident.component.spec.ts
│   │   │   │   │   └── change-to-incident.component.ts
│   │   │   │   ├── change-to-incident-view
│   │   │   │   │   ├── change-to-incident-view.component.html
│   │   │   │   │   ├── change-to-incident-view.component.scss
│   │   │   │   │   ├── change-to-incident-view.component.spec.ts
│   │   │   │   │   └── change-to-incident-view.component.ts
│   │   │   │   ├── change-view
│   │   │   │   │   ├── change-view.component.html
│   │   │   │   │   ├── change-view.component.scss
│   │   │   │   │   ├── change-view.component.spec.ts
│   │   │   │   │   └── change-view.component.ts
│   │   │   │   ├── change-view-attachment
│   │   │   │   │   ├── change-view-attachment.html
│   │   │   │   │   ├── change-view-attachment.scss
│   │   │   │   │   ├── change-view-attachment.spec.ts
│   │   │   │   │   └── change-view-attachment.ts
│   │   │   │   ├── create-task
│   │   │   │   │   ├── create-task.component.html
│   │   │   │   │   ├── create-task.component.scss
│   │   │   │   │   ├── create-task.component.spec.ts
│   │   │   │   │   └── create-task.component.ts
│   │   │   │   ├── select-template
│   │   │   │   │   ├── select-template.component.html
│   │   │   │   │   ├── select-template.component.scss
│   │   │   │   │   ├── select-template.component.spec.ts
│   │   │   │   │   └── select-template.component.ts
│   │   │   │   └── view-task
│   │   │   │       ├── view-task.component.html
│   │   │   │       ├── view-task.component.scss
│   │   │   │       ├── view-task.component.spec.ts
│   │   │   │       └── view-task.component.ts
│   │   │   ├── model
│   │   │   │   └── calendar.model.ts
│   │   │   └── services
│   │   │       ├── calendar.service.ts
│   │   │       ├── change-view.service.spec.ts
│   │   │       └── change-view.service.ts
│   │   ├── incident-view
│   │   │   ├── components
│   │   │   │   ├── approval
│   │   │   │   │   ├── approval.component.html
│   │   │   │   │   ├── approval.component.scss
│   │   │   │   │   ├── approval.component.spec.ts
│   │   │   │   │   └── approval.component.ts
│   │   │   │   ├── bulk-resolve
│   │   │   │   │   ├── bulk-resolve.component.html
│   │   │   │   │   ├── bulk-resolve.component.scss
│   │   │   │   │   ├── bulk-resolve.component.spec.ts
│   │   │   │   │   └── bulk-resolve.component.ts
│   │   │   │   ├── dns-incident-view
│   │   │   │   │   ├── dns-incident-view.component.html
│   │   │   │   │   ├── dns-incident-view.component.scss
│   │   │   │   │   ├── dns-incident-view.component.spec.ts
│   │   │   │   │   └── dns-incident-view.component.ts
│   │   │   │   ├── hold-config
│   │   │   │   │   ├── hold-config.component.html
│   │   │   │   │   ├── hold-config.component.scss
│   │   │   │   │   ├── hold-config.component.spec.ts
│   │   │   │   │   └── hold-config.component.ts
│   │   │   │   ├── horizontal-timeline
│   │   │   │   │   ├── horizontal-timeline.component.html
│   │   │   │   │   ├── horizontal-timeline.component.scss
│   │   │   │   │   ├── horizontal-timeline.component.spec.ts
│   │   │   │   │   └── horizontal-timeline.component.ts
│   │   │   │   ├── incident-add
│   │   │   │   │   ├── incident-add.component.html
│   │   │   │   │   ├── incident-add.component.scss
│   │   │   │   │   ├── incident-add.component.spec.ts
│   │   │   │   │   └── incident-add.component.ts
│   │   │   │   ├── incident-assignee
│   │   │   │   │   ├── incident-assignee.component.html
│   │   │   │   │   ├── incident-assignee.component.scss
│   │   │   │   │   ├── incident-assignee.component.spec.ts
│   │   │   │   │   └── incident-assignee.component.ts
│   │   │   │   ├── incident-attachment
│   │   │   │   │   ├── incident-attachment.component.html
│   │   │   │   │   ├── incident-attachment.component.scss
│   │   │   │   │   ├── incident-attachment.component.spec.ts
│   │   │   │   │   └── incident-attachment.component.ts
│   │   │   │   ├── incident-clone
│   │   │   │   │   ├── incident-clone.component.html
│   │   │   │   │   ├── incident-clone.component.scss
│   │   │   │   │   ├── incident-clone.component.spec.ts
│   │   │   │   │   └── incident-clone.component.ts
│   │   │   │   ├── incident-comment
│   │   │   │   │   ├── incident-comment.component.html
│   │   │   │   │   ├── incident-comment.component.scss
│   │   │   │   │   ├── incident-comment.component.spec.ts
│   │   │   │   │   └── incident-comment.component.ts
│   │   │   │   ├── incident-edit
│   │   │   │   │   ├── incident-edit.component.html
│   │   │   │   │   ├── incident-edit.component.scss
│   │   │   │   │   ├── incident-edit.component.spec.ts
│   │   │   │   │   └── incident-edit.component.ts
│   │   │   │   ├── incident-edit-sidebar
│   │   │   │   │   ├── incident-edit-sidebar.component.html
│   │   │   │   │   ├── incident-edit-sidebar.component.scss
│   │   │   │   │   ├── incident-edit-sidebar.component.spec.ts
│   │   │   │   │   └── incident-edit-sidebar.component.ts
│   │   │   │   ├── incident-history
│   │   │   │   │   ├── incident-history.component.html
│   │   │   │   │   ├── incident-history.component.scss
│   │   │   │   │   ├── incident-history.component.spec.ts
│   │   │   │   │   └── incident-history.component.ts
│   │   │   │   ├── incident-interaction
│   │   │   │   │   ├── incident-interaction.component.html
│   │   │   │   │   ├── incident-interaction.component.scss
│   │   │   │   │   ├── incident-interaction.component.spec.ts
│   │   │   │   │   └── incident-interaction.component.ts
│   │   │   │   ├── incident-kb-solution
│   │   │   │   │   ├── incident-kb-solution.component.html
│   │   │   │   │   ├── incident-kb-solution.component.scss
│   │   │   │   │   ├── incident-kb-solution.component.spec.ts
│   │   │   │   │   └── incident-kb-solution.component.ts
│   │   │   │   ├── incident-quick-edit
│   │   │   │   │   ├── incident-quick-edit.component.html
│   │   │   │   │   ├── incident-quick-edit.component.scss
│   │   │   │   │   ├── incident-quick-edit.component.spec.ts
│   │   │   │   │   └── incident-quick-edit.component.ts
│   │   │   │   ├── incident-relations
│   │   │   │   │   └── incident-relations.component.ts
│   │   │   │   ├── incident-resolve
│   │   │   │   │   ├── incident-resolve.component.html
│   │   │   │   │   ├── incident-resolve.component.scss
│   │   │   │   │   ├── incident-resolve.component.spec.ts
│   │   │   │   │   └── incident-resolve.component.ts
│   │   │   │   ├── incident-sekeleton
│   │   │   │   │   ├── incident-sekeleton.component.html
│   │   │   │   │   ├── incident-sekeleton.component.scss
│   │   │   │   │   ├── incident-sekeleton.component.spec.ts
│   │   │   │   │   └── incident-sekeleton.component.ts
│   │   │   │   ├── incident-to-change
│   │   │   │   │   ├── incident-to-change.component.html
│   │   │   │   │   ├── incident-to-change.component.scss
│   │   │   │   │   ├── incident-to-change.component.spec.ts
│   │   │   │   │   └── incident-to-change.component.ts
│   │   │   │   ├── incident-to-problem
│   │   │   │   │   ├── incident-to-problem.component.html
│   │   │   │   │   ├── incident-to-problem.component.scss
│   │   │   │   │   ├── incident-to-problem.component.spec.ts
│   │   │   │   │   └── incident-to-problem.component.ts
│   │   │   │   ├── incident-to-request
│   │   │   │   │   ├── incident-to-request.component.html
│   │   │   │   │   ├── incident-to-request.component.scss
│   │   │   │   │   ├── incident-to-request.component.spec.ts
│   │   │   │   │   └── incident-to-request.component.ts
│   │   │   │   ├── incident-to-request-view
│   │   │   │   │   ├── incident-to-request-view.component.html
│   │   │   │   │   ├── incident-to-request-view.component.scss
│   │   │   │   │   ├── incident-to-request-view.component.spec.ts
│   │   │   │   │   └── incident-to-request-view.component.ts
│   │   │   │   ├── incident-view-attachment
│   │   │   │   │   ├── incident-view-attachment.html
│   │   │   │   │   ├── incident-view-attachment.scss
│   │   │   │   │   ├── incident-view-attachment.spec.ts
│   │   │   │   │   └── incident-view-attachment.ts
│   │   │   │   ├── merge-incident
│   │   │   │   │   ├── merge-incident.component.html
│   │   │   │   │   ├── merge-incident.component.scss
│   │   │   │   │   ├── merge-incident.component.spec.ts
│   │   │   │   │   └── merge-incident.component.ts
│   │   │   │   ├── sla-info-view
│   │   │   │   │   ├── sla-info-view.component.html
│   │   │   │   │   ├── sla-info-view.component.scss
│   │   │   │   │   ├── sla-info-view.component.spec.ts
│   │   │   │   │   └── sla-info-view.component.ts
│   │   │   │   └── tag
│   │   │   │       ├── tag.component.html
│   │   │   │       ├── tag.component.scss
│   │   │   │       ├── tag.component.spec.ts
│   │   │   │       └── tag.component.ts
│   │   │   ├── incident-view-routing.module.ts
│   │   │   ├── incident-view.module.ts
│   │   │   ├── services
│   │   │   │   ├── incident-view.service.spec.ts
│   │   │   │   └── incident-view.service.ts
│   │   │   └── types
│   │   │       └── config.ts
│   │   ├── problem
│   │   │   ├── components
│   │   │   │   ├── dns-problem-view
│   │   │   │   │   ├── dns-problem-view.component.html
│   │   │   │   │   ├── dns-problem-view.component.scss
│   │   │   │   │   ├── dns-problem-view.component.spec.ts
│   │   │   │   │   └── dns-problem-view.component.ts
│   │   │   │   ├── problem-add
│   │   │   │   │   ├── problem-add.component.html
│   │   │   │   │   ├── problem-add.component.scss
│   │   │   │   │   ├── problem-add.component.spec.ts
│   │   │   │   │   └── problem-add.component.ts
│   │   │   │   ├── problem-analysis-sidebar
│   │   │   │   │   ├── problem-analysis-sidebar.component.html
│   │   │   │   │   ├── problem-analysis-sidebar.component.scss
│   │   │   │   │   ├── problem-analysis-sidebar.component.spec.ts
│   │   │   │   │   └── problem-analysis-sidebar.component.ts
│   │   │   │   ├── problem-approval
│   │   │   │   │   ├── problem-approval.component.html
│   │   │   │   │   ├── problem-approval.component.scss
│   │   │   │   │   ├── problem-approval.component.spec.ts
│   │   │   │   │   └── problem-approval.component.ts
│   │   │   │   ├── problem-assignee
│   │   │   │   │   ├── problem-assignee.component.html
│   │   │   │   │   ├── problem-assignee.component.scss
│   │   │   │   │   ├── problem-assignee.component.spec.ts
│   │   │   │   │   └── problem-assignee.component.ts
│   │   │   │   ├── problem-attachment
│   │   │   │   │   ├── problem-attachment.component.html
│   │   │   │   │   ├── problem-attachment.component.scss
│   │   │   │   │   ├── problem-attachment.component.spec.ts
│   │   │   │   │   └── problem-attachment.component.ts
│   │   │   │   ├── problem-bulk-resolve
│   │   │   │   │   ├── problem-bulk-resolve.component.html
│   │   │   │   │   ├── problem-bulk-resolve.component.scss
│   │   │   │   │   ├── problem-bulk-resolve.component.spec.ts
│   │   │   │   │   └── problem-bulk-resolve.component.ts
│   │   │   │   ├── problem-clone
│   │   │   │   │   ├── problem-clone.component.html
│   │   │   │   │   ├── problem-clone.component.scss
│   │   │   │   │   ├── problem-clone.component.spec.ts
│   │   │   │   │   └── problem-clone.component.ts
│   │   │   │   ├── problem-close
│   │   │   │   │   ├── problem-close.component.html
│   │   │   │   │   ├── problem-close.component.scss
│   │   │   │   │   ├── problem-close.component.spec.ts
│   │   │   │   │   └── problem-close.component.ts
│   │   │   │   ├── problem-comment
│   │   │   │   │   ├── problem-comment.component.html
│   │   │   │   │   ├── problem-comment.component.scss
│   │   │   │   │   ├── problem-comment.component.spec.ts
│   │   │   │   │   └── problem-comment.component.ts
│   │   │   │   ├── problem-create-task
│   │   │   │   │   ├── problem-create-task.component.html
│   │   │   │   │   ├── problem-create-task.component.scss
│   │   │   │   │   ├── problem-create-task.component.spec.ts
│   │   │   │   │   └── problem-create-task.component.ts
│   │   │   │   ├── problem-edit
│   │   │   │   │   ├── problem-edit.component.html
│   │   │   │   │   ├── problem-edit.component.scss
│   │   │   │   │   ├── problem-edit.component.spec.ts
│   │   │   │   │   └── problem-edit.component.ts
│   │   │   │   ├── problem-edit-sidebar
│   │   │   │   │   ├── problem-edit-sidebar.component.html
│   │   │   │   │   ├── problem-edit-sidebar.component.scss
│   │   │   │   │   ├── problem-edit-sidebar.component.spec.ts
│   │   │   │   │   └── problem-edit-sidebar.component.ts
│   │   │   │   ├── problem-history
│   │   │   │   │   ├── problem-history.component.html
│   │   │   │   │   ├── problem-history.component.scss
│   │   │   │   │   ├── problem-history.component.spec.ts
│   │   │   │   │   └── problem-history.component.ts
│   │   │   │   ├── problem-interaction
│   │   │   │   │   ├── problem-interaction.component.html
│   │   │   │   │   ├── problem-interaction.component.scss
│   │   │   │   │   ├── problem-interaction.component.spec.ts
│   │   │   │   │   └── problem-interaction.component.ts
│   │   │   │   ├── problem-kb-solution
│   │   │   │   │   ├── problem-kb-solution.component.html
│   │   │   │   │   ├── problem-kb-solution.component.scss
│   │   │   │   │   ├── problem-kb-solution.component.spec.ts
│   │   │   │   │   └── problem-kb-solution.component.ts
│   │   │   │   ├── problem-new-risk-sidebar
│   │   │   │   │   ├── problem-new-risk-sidebar.component.html
│   │   │   │   │   ├── problem-new-risk-sidebar.component.scss
│   │   │   │   │   ├── problem-new-risk-sidebar.component.spec.ts
│   │   │   │   │   └── problem-new-risk-sidebar.component.ts
│   │   │   │   ├── problem-quick-edit
│   │   │   │   │   ├── problem-quick-edit.component.html
│   │   │   │   │   ├── problem-quick-edit.component.scss
│   │   │   │   │   ├── problem-quick-edit.component.spec.ts
│   │   │   │   │   └── problem-quick-edit.component.ts
│   │   │   │   ├── problem-resolve
│   │   │   │   │   ├── problem-resolve.component.html
│   │   │   │   │   ├── problem-resolve.component.scss
│   │   │   │   │   ├── problem-resolve.component.spec.ts
│   │   │   │   │   └── problem-resolve.component.ts
│   │   │   │   ├── problem-skeleton
│   │   │   │   │   ├── problem-skeleton.component.html
│   │   │   │   │   ├── problem-skeleton.component.scss
│   │   │   │   │   ├── problem-skeleton.component.spec.ts
│   │   │   │   │   └── problem-skeleton.component.ts
│   │   │   │   ├── problem-solution-sidebar
│   │   │   │   │   ├── problem-solution-sidebar.component.html
│   │   │   │   │   ├── problem-solution-sidebar.component.scss
│   │   │   │   │   ├── problem-solution-sidebar.component.spec.ts
│   │   │   │   │   └── problem-solution-sidebar.component.ts
│   │   │   │   ├── problem-task-list
│   │   │   │   │   ├── problem-task-list.component.html
│   │   │   │   │   ├── problem-task-list.component.scss
│   │   │   │   │   ├── problem-task-list.component.spec.ts
│   │   │   │   │   └── problem-task-list.component.ts
│   │   │   │   ├── problem-to-change
│   │   │   │   │   ├── problem-to-change.component.html
│   │   │   │   │   ├── problem-to-change.component.scss
│   │   │   │   │   ├── problem-to-change.component.spec.ts
│   │   │   │   │   └── problem-to-change.component.ts
│   │   │   │   ├── problem-to-incident
│   │   │   │   │   ├── problem-to-incident.component.html
│   │   │   │   │   ├── problem-to-incident.component.scss
│   │   │   │   │   ├── problem-to-incident.component.spec.ts
│   │   │   │   │   └── problem-to-incident.component.ts
│   │   │   │   ├── problem-to-incident-view
│   │   │   │   │   ├── problem-to-incident-view.component.html
│   │   │   │   │   ├── problem-to-incident-view.component.scss
│   │   │   │   │   ├── problem-to-incident-view.component.spec.ts
│   │   │   │   │   └── problem-to-incident-view.component.ts
│   │   │   │   ├── problem-view-attachment
│   │   │   │   │   ├── problem-view-attachment.component.html
│   │   │   │   │   ├── problem-view-attachment.component.scss
│   │   │   │   │   ├── problem-view-attachment.component.spec.ts
│   │   │   │   │   └── problem-view-attachment.component.ts
│   │   │   │   ├── view-draft-sidebar
│   │   │   │   │   ├── view-draft-sidebar.component.html
│   │   │   │   │   ├── view-draft-sidebar.component.scss
│   │   │   │   │   ├── view-draft-sidebar.component.spec.ts
│   │   │   │   │   └── view-draft-sidebar.component.ts
│   │   │   │   └── view-task
│   │   │   │       ├── view-task.component.html
│   │   │   │       ├── view-task.component.scss
│   │   │   │       ├── view-task.component.spec.ts
│   │   │   │       └── view-task.component.ts
│   │   │   ├── problem-routing.module.ts
│   │   │   ├── problem.module.ts
│   │   │   └── services
│   │   │       ├── problem.service.spec.ts
│   │   │       └── problem.service.ts
│   │   ├── release-manage
│   │   │   ├── components
│   │   │   │   ├── add-issue
│   │   │   │   │   ├── add-issue.component.html
│   │   │   │   │   ├── add-issue.component.scss
│   │   │   │   │   ├── add-issue.component.spec.ts
│   │   │   │   │   └── add-issue.component.ts
│   │   │   │   ├── add-release
│   │   │   │   │   ├── add-release.component.html
│   │   │   │   │   ├── add-release.component.scss
│   │   │   │   │   ├── add-release.component.spec.ts
│   │   │   │   │   └── add-release.component.ts
│   │   │   │   ├── add-task
│   │   │   │   │   ├── add-task.component.html
│   │   │   │   │   ├── add-task.component.scss
│   │   │   │   │   ├── add-task.component.spec.ts
│   │   │   │   │   └── add-task.component.ts
│   │   │   │   ├── create-add-task
│   │   │   │   │   ├── create-add-task.component.html
│   │   │   │   │   ├── create-add-task.component.scss
│   │   │   │   │   ├── create-add-task.component.spec.ts
│   │   │   │   │   └── create-add-task.component.ts
│   │   │   │   ├── feature-new-task
│   │   │   │   │   ├── feature-new-task.component.html
│   │   │   │   │   ├── feature-new-task.component.scss
│   │   │   │   │   ├── feature-new-task.component.spec.ts
│   │   │   │   │   └── feature-new-task.component.ts
│   │   │   │   ├── new-issue
│   │   │   │   │   ├── new-issue.component.html
│   │   │   │   │   ├── new-issue.component.scss
│   │   │   │   │   ├── new-issue.component.spec.ts
│   │   │   │   │   └── new-issue.component.ts
│   │   │   │   ├── new-task
│   │   │   │   │   ├── new-task.component.html
│   │   │   │   │   ├── new-task.component.scss
│   │   │   │   │   ├── new-task.component.spec.ts
│   │   │   │   │   └── new-task.component.ts
│   │   │   │   ├── quick-edit
│   │   │   │   │   ├── quick-edit.component.html
│   │   │   │   │   ├── quick-edit.component.scss
│   │   │   │   │   ├── quick-edit.component.spec.ts
│   │   │   │   │   └── quick-edit.component.ts
│   │   │   │   ├── relate-task
│   │   │   │   │   ├── relate-task.component.html
│   │   │   │   │   ├── relate-task.component.scss
│   │   │   │   │   ├── relate-task.component.spec.ts
│   │   │   │   │   └── relate-task.component.ts
│   │   │   │   ├── release-approval
│   │   │   │   │   ├── release-approval.component.html
│   │   │   │   │   ├── release-approval.component.scss
│   │   │   │   │   ├── release-approval.component.spec.ts
│   │   │   │   │   └── release-approval.component.ts
│   │   │   │   ├── release-assignee
│   │   │   │   │   ├── release-assignee.component.html
│   │   │   │   │   ├── release-assignee.component.scss
│   │   │   │   │   ├── release-assignee.component.spec.ts
│   │   │   │   │   └── release-assignee.component.ts
│   │   │   │   ├── release-attachment
│   │   │   │   │   ├── release-attachment.component.html
│   │   │   │   │   ├── release-attachment.component.scss
│   │   │   │   │   ├── release-attachment.component.spec.ts
│   │   │   │   │   └── release-attachment.component.ts
│   │   │   │   ├── release-close
│   │   │   │   │   ├── release-close.component.html
│   │   │   │   │   ├── release-close.component.scss
│   │   │   │   │   ├── release-close.component.spec.ts
│   │   │   │   │   └── release-close.component.ts
│   │   │   │   ├── release-comment
│   │   │   │   │   ├── release-comment.component.html
│   │   │   │   │   ├── release-comment.component.scss
│   │   │   │   │   ├── release-comment.component.spec.ts
│   │   │   │   │   └── release-comment.component.ts
│   │   │   │   ├── release-edit-sidebar
│   │   │   │   │   ├── release-edit-sidebar.component.html
│   │   │   │   │   ├── release-edit-sidebar.component.scss
│   │   │   │   │   ├── release-edit-sidebar.component.spec.ts
│   │   │   │   │   └── release-edit-sidebar.component.ts
│   │   │   │   ├── release-history
│   │   │   │   │   ├── release-history.component.html
│   │   │   │   │   ├── release-history.component.scss
│   │   │   │   │   ├── release-history.component.spec.ts
│   │   │   │   │   └── release-history.component.ts
│   │   │   │   ├── release-interaction
│   │   │   │   │   ├── release-interaction.component.html
│   │   │   │   │   ├── release-interaction.component.scss
│   │   │   │   │   ├── release-interaction.component.spec.ts
│   │   │   │   │   └── release-interaction.component.ts
│   │   │   │   ├── release-risk-level
│   │   │   │   │   ├── release-risk-level.component.html
│   │   │   │   │   ├── release-risk-level.component.scss
│   │   │   │   │   ├── release-risk-level.component.spec.ts
│   │   │   │   │   └── release-risk-level.component.ts
│   │   │   │   ├── release-skeleton
│   │   │   │   │   ├── release-skeleton.component.html
│   │   │   │   │   ├── release-skeleton.component.scss
│   │   │   │   │   ├── release-skeleton.component.spec.ts
│   │   │   │   │   └── release-skeleton.component.ts
│   │   │   │   ├── release-view
│   │   │   │   │   ├── release-view.component.html
│   │   │   │   │   ├── release-view.component.scss
│   │   │   │   │   ├── release-view.component.spec.ts
│   │   │   │   │   └── release-view.component.ts
│   │   │   │   ├── release-view-attachment
│   │   │   │   │   ├── release-view-attachment.html
│   │   │   │   │   ├── release-view-attachment.scss
│   │   │   │   │   ├── release-view-attachment.spec.ts
│   │   │   │   │   └── release-view-attachment.ts
│   │   │   │   ├── release-view-edit
│   │   │   │   │   ├── release-view-edit.component.html
│   │   │   │   │   ├── release-view-edit.component.scss
│   │   │   │   │   ├── release-view-edit.component.spec.ts
│   │   │   │   │   └── release-view-edit.component.ts
│   │   │   │   └── view-task
│   │   │   │       ├── view-task.component.html
│   │   │   │       ├── view-task.component.scss
│   │   │   │       ├── view-task.component.spec.ts
│   │   │   │       └── view-task.component.ts
│   │   │   ├── release-routing.module.ts
│   │   │   ├── release.module.ts
│   │   │   └── services
│   │   │       ├── release-services.service.spec.ts
│   │   │       └── release-services.service.ts
│   │   └── request
│   │       ├── components
│   │       │   ├── add-request
│   │       │   │   ├── add-request.component.html
│   │       │   │   ├── add-request.component.scss
│   │       │   │   ├── add-request.component.spec.ts
│   │       │   │   └── add-request.component.ts
│   │       │   ├── allocate-new-asset-list
│   │       │   │   ├── allocate-new-asset-list.component.html
│   │       │   │   ├── allocate-new-asset-list.component.scss
│   │       │   │   ├── allocate-new-asset-list.component.spec.ts
│   │       │   │   └── allocate-new-asset-list.component.ts
│   │       │   ├── allocate-new-asset-sidebar
│   │       │   │   ├── allocate-new-asset-sidebar.component.html
│   │       │   │   ├── allocate-new-asset-sidebar.component.scss
│   │       │   │   ├── allocate-new-asset-sidebar.component.spec.ts
│   │       │   │   └── allocate-new-asset-sidebar.component.ts
│   │       │   ├── asset-upgrade-sidebar
│   │       │   │   ├── asset-upgrade-sidebar.component.html
│   │       │   │   ├── asset-upgrade-sidebar.component.scss
│   │       │   │   ├── asset-upgrade-sidebar.component.spec.ts
│   │       │   │   └── asset-upgrade-sidebar.component.ts
│   │       │   ├── assign-name-design
│   │       │   │   ├── assign-name-design.component.html
│   │       │   │   ├── assign-name-design.component.scss
│   │       │   │   ├── assign-name-design.component.spec.ts
│   │       │   │   └── assign-name-design.component.ts
│   │       │   ├── impact-design
│   │       │   │   ├── impact-design.component.html
│   │       │   │   ├── impact-design.component.scss
│   │       │   │   ├── impact-design.component.spec.ts
│   │       │   │   └── impact-design.component.ts
│   │       │   ├── inventory-sidebar
│   │       │   │   ├── inventory-sidebar.component.html
│   │       │   │   ├── inventory-sidebar.component.scss
│   │       │   │   ├── inventory-sidebar.component.spec.ts
│   │       │   │   └── inventory-sidebar.component.ts
│   │       │   ├── name-design
│   │       │   │   ├── name-design.component.html
│   │       │   │   ├── name-design.component.scss
│   │       │   │   ├── name-design.component.spec.ts
│   │       │   │   └── name-design.component.ts
│   │       │   ├── request-approval
│   │       │   │   ├── request-approval.component.html
│   │       │   │   ├── request-approval.component.scss
│   │       │   │   ├── request-approval.component.spec.ts
│   │       │   │   └── request-approval.component.ts
│   │       │   ├── request-assignee
│   │       │   │   ├── request-assignee.component.html
│   │       │   │   ├── request-assignee.component.scss
│   │       │   │   ├── request-assignee.component.spec.ts
│   │       │   │   └── request-assignee.component.ts
│   │       │   ├── request-attachment
│   │       │   │   ├── request-attachment.component.html
│   │       │   │   ├── request-attachment.component.scss
│   │       │   │   ├── request-attachment.component.spec.ts
│   │       │   │   └── request-attachment.component.ts
│   │       │   ├── request-bulk-resolve
│   │       │   │   ├── request-bulk-resolve.component.html
│   │       │   │   ├── request-bulk-resolve.component.scss
│   │       │   │   ├── request-bulk-resolve.component.spec.ts
│   │       │   │   └── request-bulk-resolve.component.ts
│   │       │   ├── request-clone
│   │       │   │   ├── request-clone.component.html
│   │       │   │   ├── request-clone.component.scss
│   │       │   │   ├── request-clone.component.spec.ts
│   │       │   │   └── request-clone.component.ts
│   │       │   ├── request-close
│   │       │   │   ├── request-close.component.html
│   │       │   │   ├── request-close.component.scss
│   │       │   │   ├── request-close.component.spec.ts
│   │       │   │   └── request-close.component.ts
│   │       │   ├── request-comment
│   │       │   │   ├── request-comment.component.html
│   │       │   │   ├── request-comment.component.scss
│   │       │   │   ├── request-comment.component.spec.ts
│   │       │   │   └── request-comment.component.ts
│   │       │   ├── request-edit-sidebar
│   │       │   │   ├── request-edit-sidebar.component.html
│   │       │   │   ├── request-edit-sidebar.component.scss
│   │       │   │   ├── request-edit-sidebar.component.spec.ts
│   │       │   │   └── request-edit-sidebar.component.ts
│   │       │   ├── request-history
│   │       │   │   ├── request-history.component.html
│   │       │   │   ├── request-history.component.scss
│   │       │   │   ├── request-history.component.spec.ts
│   │       │   │   └── request-history.component.ts
│   │       │   ├── request-interaction
│   │       │   │   ├── request-interaction.component.html
│   │       │   │   ├── request-interaction.component.scss
│   │       │   │   ├── request-interaction.component.spec.ts
│   │       │   │   └── request-interaction.component.ts
│   │       │   ├── request-kb-solution
│   │       │   │   ├── request-kb-solution.component.html
│   │       │   │   ├── request-kb-solution.component.scss
│   │       │   │   ├── request-kb-solution.component.spec.ts
│   │       │   │   └── request-kb-solution.component.ts
│   │       │   ├── request-list
│   │       │   │   ├── request-list.component.html
│   │       │   │   ├── request-list.component.scss
│   │       │   │   ├── request-list.component.spec.ts
│   │       │   │   └── request-list.component.ts
│   │       │   ├── request-merge
│   │       │   │   ├── request-merge.component.html
│   │       │   │   ├── request-merge.component.scss
│   │       │   │   ├── request-merge.component.spec.ts
│   │       │   │   └── request-merge.component.ts
│   │       │   ├── request-quick-edit
│   │       │   │   ├── request-quick-edit.component.html
│   │       │   │   ├── request-quick-edit.component.scss
│   │       │   │   ├── request-quick-edit.component.spec.ts
│   │       │   │   └── request-quick-edit.component.ts
│   │       │   ├── request-resolve
│   │       │   │   ├── request-resolve.component.html
│   │       │   │   ├── request-resolve.component.scss
│   │       │   │   ├── request-resolve.component.spec.ts
│   │       │   │   └── request-resolve.component.ts
│   │       │   ├── request-sidebar
│   │       │   │   ├── request-sidebar.component.html
│   │       │   │   ├── request-sidebar.component.scss
│   │       │   │   ├── request-sidebar.component.spec.ts
│   │       │   │   └── request-sidebar.component.ts
│   │       │   ├── request-skeleton
│   │       │   │   ├── request-skeleton.component.html
│   │       │   │   ├── request-skeleton.component.scss
│   │       │   │   ├── request-skeleton.component.spec.ts
│   │       │   │   └── request-skeleton.component.ts
│   │       │   ├── request-sla-info
│   │       │   │   ├── request-sla-info.component.html
│   │       │   │   ├── request-sla-info.component.scss
│   │       │   │   ├── request-sla-info.component.spec.ts
│   │       │   │   └── request-sla-info.component.ts
│   │       │   ├── request-to-change
│   │       │   │   ├── request-to-change.component.html
│   │       │   │   ├── request-to-change.component.scss
│   │       │   │   ├── request-to-change.component.spec.ts
│   │       │   │   └── request-to-change.component.ts
│   │       │   ├── request-to-incident
│   │       │   │   ├── request-to-incident.component.html
│   │       │   │   ├── request-to-incident.component.scss
│   │       │   │   ├── request-to-incident.component.spec.ts
│   │       │   │   └── request-to-incident.component.ts
│   │       │   ├── request-to-incident-view
│   │       │   │   ├── request-to-incident-view.component.html
│   │       │   │   ├── request-to-incident-view.component.scss
│   │       │   │   ├── request-to-incident-view.component.spec.ts
│   │       │   │   └── request-to-incident-view.component.ts
│   │       │   ├── request-view
│   │       │   │   ├── request-view.component.html
│   │       │   │   ├── request-view.component.scss
│   │       │   │   ├── request-view.component.spec.ts
│   │       │   │   └── request-view.component.ts
│   │       │   ├── request-view-attachment
│   │       │   │   ├── request-view-attachment.html
│   │       │   │   ├── request-view-attachment.scss
│   │       │   │   ├── request-view-attachment.spec.ts
│   │       │   │   └── request-view-attachment.ts
│   │       │   ├── requester-asset-list
│   │       │   │   ├── requester-asset-list.component.html
│   │       │   │   ├── requester-asset-list.component.scss
│   │       │   │   ├── requester-asset-list.component.spec.ts
│   │       │   │   └── requester-asset-list.component.ts
│   │       │   ├── requester-asset-sidebar
│   │       │   │   ├── requester-asset-sidebar.component.html
│   │       │   │   ├── requester-asset-sidebar.component.scss
│   │       │   │   ├── requester-asset-sidebar.component.spec.ts
│   │       │   │   └── requester-asset-sidebar.component.ts
│   │       │   ├── requester-grid-name
│   │       │   │   ├── requester-grid-name.component.html
│   │       │   │   ├── requester-grid-name.component.scss
│   │       │   │   ├── requester-grid-name.component.spec.ts
│   │       │   │   └── requester-grid-name.component.ts
│   │       │   └── resolution-overview
│   │       │       ├── resolution-overview.component.html
│   │       │       ├── resolution-overview.component.scss
│   │       │       ├── resolution-overview.component.spec.ts
│   │       │       └── resolution-overview.component.ts
│   │       ├── request-routing.module.ts
│   │       ├── request.module.ts
│   │       └── services
│   │           ├── request-view.service.spec.ts
│   │           └── request-view.service.ts
│   ├── services
│   │   ├── common.service.spec.ts
│   │   ├── common.service.ts
│   │   ├── mixpanel
│   │   │   ├── infraon-mixpanel.service.spec.ts
│   │   │   └── infraon-mixpanel.service.ts
│   │   ├── org-data-service.service.spec.ts
│   │   └── org-data-service.service.ts
│   ├── shared.module.ts
│   ├── store
│   │   ├── reducers.ts
│   │   ├── settings
│   │   │   ├── actions.ts
│   │   │   └── reducers.ts
│   │   └── user
│   │       ├── actions.ts
│   │       ├── effects.ts
│   │       └── reducers.ts
│   └── support-portal
│       ├── components
│       │   ├── create-partner
│       │   │   ├── create-partner.component.html
│       │   │   ├── create-partner.component.scss
│       │   │   └── create-partner.component.ts
│       │   ├── invite-partneruser
│       │   │   ├── invite-partneruser.component.html
│       │   │   ├── invite-partneruser.component.scss
│       │   │   ├── invite-partneruser.component.spec.ts
│       │   │   └── invite-partneruser.component.ts
│       │   ├── organization-add
│       │   │   ├── organization-add.component.html
│       │   │   ├── organization-add.component.scss
│       │   │   ├── organization-add.component.spec.ts
│       │   │   └── organization-add.component.ts
│       │   ├── organization-grid
│       │   │   ├── organization-grid.component.html
│       │   │   ├── organization-grid.component.scss
│       │   │   ├── organization-grid.component.spec.ts
│       │   │   └── organization-grid.component.ts
│       │   ├── organization-invoices
│       │   │   ├── organization-invoices.component.html
│       │   │   ├── organization-invoices.component.scss
│       │   │   ├── organization-invoices.component.spec.ts
│       │   │   └── organization-invoices.component.ts
│       │   ├── partner-name-tag
│       │   │   ├── partner-name-tag.component.html
│       │   │   ├── partner-name-tag.component.scss
│       │   │   ├── partner-name-tag.component.spec.ts
│       │   │   └── partner-name-tag.component.ts
│       │   ├── partner-operators
│       │   │   ├── partner-operators.component.html
│       │   │   ├── partner-operators.component.scss
│       │   │   ├── partner-operators.component.spec.ts
│       │   │   └── partner-operators.component.ts
│       │   ├── partners-list
│       │   │   ├── partners-list.component.html
│       │   │   ├── partners-list.component.scss
│       │   │   ├── partners-list.component.spec.ts
│       │   │   └── partners-list.component.ts
│       │   ├── support-audit
│       │   │   ├── support-audit.component.html
│       │   │   ├── support-audit.component.scss
│       │   │   ├── support-audit.component.spec.ts
│       │   │   └── support-audit.component.ts
│       │   └── support-home
│       │       ├── support-home.component.html
│       │       ├── support-home.component.scss
│       │       ├── support-home.component.spec.ts
│       │       └── support-home.component.ts
│       ├── services
│       │   ├── support-portal.service.spec.ts
│       │   └── support-portal.service.ts
│       ├── support-portal-routing.module.ts
│       └── support-portal.module.ts
├── assets
│   ├── audio
│   │   ├── incoming.ogg
│   │   └── outgoing.ogg
│   ├── fonts
│   │   ├── digital-numbers
│   │   │   └── digital-7.ttf
│   │   ├── feather
│   │   │   ├── fonts
│   │   │   │   ├── feather.eot
│   │   │   │   ├── feather.svg
│   │   │   │   ├── feather.ttf
│   │   │   │   └── feather.woff
│   │   │   └── iconfont.css
│   │   ├── flag-icon-css
│   │   │   ├── css
│   │   │   │   ├── flag-icon.css
│   │   │   │   └── flag-icon.min.css
│   │   │   ├── flags
│   │   │   │   ├── 1x1
│   │   │   │   │   ├── ad.svg
│   │   │   │   │   ├── ae.svg
│   │   │   │   │   ├── af.svg
│   │   │   │   │   ├── ag.svg
│   │   │   │   │   ├── ai.svg
│   │   │   │   │   ├── al.svg
│   │   │   │   │   ├── am.svg
│   │   │   │   │   ├── ao.svg
│   │   │   │   │   ├── aq.svg
│   │   │   │   │   ├── ar.svg
│   │   │   │   │   ├── as.svg
│   │   │   │   │   ├── at.svg
│   │   │   │   │   ├── au.svg
│   │   │   │   │   ├── aw.svg
│   │   │   │   │   ├── ax.svg
│   │   │   │   │   ├── az.svg
│   │   │   │   │   ├── ba.svg
│   │   │   │   │   ├── bb.svg
│   │   │   │   │   ├── bd.svg
│   │   │   │   │   ├── be.svg
│   │   │   │   │   ├── bf.svg
│   │   │   │   │   ├── bg.svg
│   │   │   │   │   ├── bh.svg
│   │   │   │   │   ├── bi.svg
│   │   │   │   │   ├── bj.svg
│   │   │   │   │   ├── bl.svg
│   │   │   │   │   ├── bm.svg
│   │   │   │   │   ├── bn.svg
│   │   │   │   │   ├── bo.svg
│   │   │   │   │   ├── bq.svg
│   │   │   │   │   ├── br.svg
│   │   │   │   │   ├── bs.svg
│   │   │   │   │   ├── bt.svg
│   │   │   │   │   ├── bv.svg
│   │   │   │   │   ├── bw.svg
│   │   │   │   │   ├── by.svg
│   │   │   │   │   ├── bz.svg
│   │   │   │   │   ├── ca.svg
│   │   │   │   │   ├── cc.svg
│   │   │   │   │   ├── cd.svg
│   │   │   │   │   ├── cf.svg
│   │   │   │   │   ├── cg.svg
│   │   │   │   │   ├── ch.svg
│   │   │   │   │   ├── ci.svg
│   │   │   │   │   ├── ck.svg
│   │   │   │   │   ├── cl.svg
│   │   │   │   │   ├── cm.svg
│   │   │   │   │   ├── cn.svg
│   │   │   │   │   ├── co.svg
│   │   │   │   │   ├── cr.svg
│   │   │   │   │   ├── cu.svg
│   │   │   │   │   ├── cv.svg
│   │   │   │   │   ├── cw.svg
│   │   │   │   │   ├── cx.svg
│   │   │   │   │   ├── cy.svg
│   │   │   │   │   ├── cz.svg
│   │   │   │   │   ├── de.svg
│   │   │   │   │   ├── dj.svg
│   │   │   │   │   ├── dk.svg
│   │   │   │   │   ├── dm.svg
│   │   │   │   │   ├── do.svg
│   │   │   │   │   ├── dz.svg
│   │   │   │   │   ├── ec.svg
│   │   │   │   │   ├── ee.svg
│   │   │   │   │   ├── eg.svg
│   │   │   │   │   ├── eh.svg
│   │   │   │   │   ├── er.svg
│   │   │   │   │   ├── es.svg
│   │   │   │   │   ├── et.svg
│   │   │   │   │   ├── eu.svg
│   │   │   │   │   ├── fi.svg
│   │   │   │   │   ├── fj.svg
│   │   │   │   │   ├── fk.svg
│   │   │   │   │   ├── fm.svg
│   │   │   │   │   ├── fo.svg
│   │   │   │   │   ├── fr.svg
│   │   │   │   │   ├── ga.svg
│   │   │   │   │   ├── gb-eng.svg
│   │   │   │   │   ├── gb-sct.svg
│   │   │   │   │   ├── gb-wls.svg
│   │   │   │   │   ├── gb.svg
│   │   │   │   │   ├── gd.svg
│   │   │   │   │   ├── ge.svg
│   │   │   │   │   ├── gf.svg
│   │   │   │   │   ├── gg.svg
│   │   │   │   │   ├── gh.svg
│   │   │   │   │   ├── gi.svg
│   │   │   │   │   ├── gl.svg
│   │   │   │   │   ├── gm.svg
│   │   │   │   │   ├── gn.svg
│   │   │   │   │   ├── gp.svg
│   │   │   │   │   ├── gq.svg
│   │   │   │   │   ├── gr.svg
│   │   │   │   │   ├── gs.svg
│   │   │   │   │   ├── gt.svg
│   │   │   │   │   ├── gu.svg
│   │   │   │   │   ├── gw.svg
│   │   │   │   │   ├── gy.svg
│   │   │   │   │   ├── hk.svg
│   │   │   │   │   ├── hm.svg
│   │   │   │   │   ├── hn.svg
│   │   │   │   │   ├── hr.svg
│   │   │   │   │   ├── ht.svg
│   │   │   │   │   ├── hu.svg
│   │   │   │   │   ├── id.svg
│   │   │   │   │   ├── ie.svg
│   │   │   │   │   ├── il.svg
│   │   │   │   │   ├── im.svg
│   │   │   │   │   ├── in.svg
│   │   │   │   │   ├── io.svg
│   │   │   │   │   ├── iq.svg
│   │   │   │   │   ├── ir.svg
│   │   │   │   │   ├── is.svg
│   │   │   │   │   ├── it.svg
│   │   │   │   │   ├── je.svg
│   │   │   │   │   ├── jm.svg
│   │   │   │   │   ├── jo.svg
│   │   │   │   │   ├── jp.svg
│   │   │   │   │   ├── ke.svg
│   │   │   │   │   ├── kg.svg
│   │   │   │   │   ├── kh.svg
│   │   │   │   │   ├── ki.svg
│   │   │   │   │   ├── km.svg
│   │   │   │   │   ├── kn.svg
│   │   │   │   │   ├── kp.svg
│   │   │   │   │   ├── kr.svg
│   │   │   │   │   ├── kw.svg
│   │   │   │   │   ├── ky.svg
│   │   │   │   │   ├── kz.svg
│   │   │   │   │   ├── la.svg
│   │   │   │   │   ├── lb.svg
│   │   │   │   │   ├── lc.svg
│   │   │   │   │   ├── li.svg
│   │   │   │   │   ├── lk.svg
│   │   │   │   │   ├── lr.svg
│   │   │   │   │   ├── ls.svg
│   │   │   │   │   ├── lt.svg
│   │   │   │   │   ├── lu.svg
│   │   │   │   │   ├── lv.svg
│   │   │   │   │   ├── ly.svg
│   │   │   │   │   ├── ma.svg
│   │   │   │   │   ├── mc.svg
│   │   │   │   │   ├── md.svg
│   │   │   │   │   ├── me.svg
│   │   │   │   │   ├── mf.svg
│   │   │   │   │   ├── mg.svg
│   │   │   │   │   ├── mh.svg
│   │   │   │   │   ├── mk.svg
│   │   │   │   │   ├── ml.svg
│   │   │   │   │   ├── mm.svg
│   │   │   │   │   ├── mn.svg
│   │   │   │   │   ├── mo.svg
│   │   │   │   │   ├── mp.svg
│   │   │   │   │   ├── mq.svg
│   │   │   │   │   ├── mr.svg
│   │   │   │   │   ├── ms.svg
│   │   │   │   │   ├── mt.svg
│   │   │   │   │   ├── mu.svg
│   │   │   │   │   ├── mv.svg
│   │   │   │   │   ├── mw.svg
│   │   │   │   │   ├── mx.svg
│   │   │   │   │   ├── my.svg
│   │   │   │   │   ├── mz.svg
│   │   │   │   │   ├── na.svg
│   │   │   │   │   ├── nc.svg
│   │   │   │   │   ├── ne.svg
│   │   │   │   │   ├── nf.svg
│   │   │   │   │   ├── ng.svg
│   │   │   │   │   ├── ni.svg
│   │   │   │   │   ├── nl.svg
│   │   │   │   │   ├── no.svg
│   │   │   │   │   ├── np.svg
│   │   │   │   │   ├── nr.svg
│   │   │   │   │   ├── nu.svg
│   │   │   │   │   ├── nz.svg
│   │   │   │   │   ├── om.svg
│   │   │   │   │   ├── pa.svg
│   │   │   │   │   ├── pe.svg
│   │   │   │   │   ├── pf.svg
│   │   │   │   │   ├── pg.svg
│   │   │   │   │   ├── ph.svg
│   │   │   │   │   ├── pk.svg
│   │   │   │   │   ├── pl.svg
│   │   │   │   │   ├── pm.svg
│   │   │   │   │   ├── pn.svg
│   │   │   │   │   ├── pr.svg
│   │   │   │   │   ├── ps.svg
│   │   │   │   │   ├── pt.svg
│   │   │   │   │   ├── pw.svg
│   │   │   │   │   ├── py.svg
│   │   │   │   │   ├── qa.svg
│   │   │   │   │   ├── re.svg
│   │   │   │   │   ├── ro.svg
│   │   │   │   │   ├── rs.svg
│   │   │   │   │   ├── ru.svg
│   │   │   │   │   ├── rw.svg
│   │   │   │   │   ├── sa.svg
│   │   │   │   │   ├── sb.svg
│   │   │   │   │   ├── sc.svg
│   │   │   │   │   ├── sd.svg
│   │   │   │   │   ├── se.svg
│   │   │   │   │   ├── sg.svg
│   │   │   │   │   ├── sh.svg
│   │   │   │   │   ├── si.svg
│   │   │   │   │   ├── sj.svg
│   │   │   │   │   ├── sk.svg
│   │   │   │   │   ├── sl.svg
│   │   │   │   │   ├── sm.svg
│   │   │   │   │   ├── sn.svg
│   │   │   │   │   ├── so.svg
│   │   │   │   │   ├── sr.svg
│   │   │   │   │   ├── ss.svg
│   │   │   │   │   ├── st.svg
│   │   │   │   │   ├── sv.svg
│   │   │   │   │   ├── sx.svg
│   │   │   │   │   ├── sy.svg
│   │   │   │   │   ├── sz.svg
│   │   │   │   │   ├── tc.svg
│   │   │   │   │   ├── td.svg
│   │   │   │   │   ├── tf.svg
│   │   │   │   │   ├── tg.svg
│   │   │   │   │   ├── th.svg
│   │   │   │   │   ├── tj.svg
│   │   │   │   │   ├── tk.svg
│   │   │   │   │   ├── tl.svg
│   │   │   │   │   ├── tm.svg
│   │   │   │   │   ├── tn.svg
│   │   │   │   │   ├── to.svg
│   │   │   │   │   ├── tr.svg
│   │   │   │   │   ├── tt.svg
│   │   │   │   │   ├── tv.svg
│   │   │   │   │   ├── tw.svg
│   │   │   │   │   ├── tz.svg
│   │   │   │   │   ├── ua.svg
│   │   │   │   │   ├── ug.svg
│   │   │   │   │   ├── um.svg
│   │   │   │   │   ├── us.svg
│   │   │   │   │   ├── uy.svg
│   │   │   │   │   ├── uz.svg
│   │   │   │   │   ├── va.svg
│   │   │   │   │   ├── vc.svg
│   │   │   │   │   ├── ve.svg
│   │   │   │   │   ├── vg.svg
│   │   │   │   │   ├── vi.svg
│   │   │   │   │   ├── vn.svg
│   │   │   │   │   ├── vu.svg
│   │   │   │   │   ├── wf.svg
│   │   │   │   │   ├── ws.svg
│   │   │   │   │   ├── ye.svg
│   │   │   │   │   ├── yt.svg
│   │   │   │   │   ├── za.svg
│   │   │   │   │   ├── zm.svg
│   │   │   │   │   ├── zw.svg
│   │   │   │   │   └── zz.svg
│   │   │   │   └── 4x3
│   │   │   │       ├── ad.svg
│   │   │   │       ├── ae.svg
│   │   │   │       ├── af.svg
│   │   │   │       ├── ag.svg
│   │   │   │       ├── ai.svg
│   │   │   │       ├── al.svg
│   │   │   │       ├── am.svg
│   │   │   │       ├── ao.svg
│   │   │   │       ├── aq.svg
│   │   │   │       ├── ar.svg
│   │   │   │       ├── as.svg
│   │   │   │       ├── at.svg
│   │   │   │       ├── au.svg
│   │   │   │       ├── aw.svg
│   │   │   │       ├── ax.svg
│   │   │   │       ├── az.svg
│   │   │   │       ├── ba.svg
│   │   │   │       ├── bb.svg
│   │   │   │       ├── bd.svg
│   │   │   │       ├── be.svg
│   │   │   │       ├── bf.svg
│   │   │   │       ├── bg.svg
│   │   │   │       ├── bh.svg
│   │   │   │       ├── bi.svg
│   │   │   │       ├── bj.svg
│   │   │   │       ├── bl.svg
│   │   │   │       ├── bm.svg
│   │   │   │       ├── bn.svg
│   │   │   │       ├── bo.svg
│   │   │   │       ├── bq.svg
│   │   │   │       ├── br.svg
│   │   │   │       ├── bs.svg
│   │   │   │       ├── bt.svg
│   │   │   │       ├── bv.svg
│   │   │   │       ├── bw.svg
│   │   │   │       ├── by.svg
│   │   │   │       ├── bz.svg
│   │   │   │       ├── ca.svg
│   │   │   │       ├── cc.svg
│   │   │   │       ├── cd.svg
│   │   │   │       ├── cf.svg
│   │   │   │       ├── cg.svg
│   │   │   │       ├── ch.svg
│   │   │   │       ├── ci.svg
│   │   │   │       ├── ck.svg
│   │   │   │       ├── cl.svg
│   │   │   │       ├── cm.svg
│   │   │   │       ├── cn.svg
│   │   │   │       ├── co.svg
│   │   │   │       ├── cr.svg
│   │   │   │       ├── cu.svg
│   │   │   │       ├── cv.svg
│   │   │   │       ├── cw.svg
│   │   │   │       ├── cx.svg
│   │   │   │       ├── cy.svg
│   │   │   │       ├── cz.svg
│   │   │   │       ├── de.svg
│   │   │   │       ├── dj.svg
│   │   │   │       ├── dk.svg
│   │   │   │       ├── dm.svg
│   │   │   │       ├── do.svg
│   │   │   │       ├── dz.svg
│   │   │   │       ├── ec.svg
│   │   │   │       ├── ee.svg
│   │   │   │       ├── eg.svg
│   │   │   │       ├── eh.svg
│   │   │   │       ├── er.svg
│   │   │   │       ├── es.svg
│   │   │   │       ├── et.svg
│   │   │   │       ├── eu.svg
│   │   │   │       ├── fi.svg
│   │   │   │       ├── fj.svg
│   │   │   │       ├── fk.svg
│   │   │   │       ├── fm.svg
│   │   │   │       ├── fo.svg
│   │   │   │       ├── fr.svg
│   │   │   │       ├── ga.svg
│   │   │   │       ├── gb-eng.svg
│   │   │   │       ├── gb-sct.svg
│   │   │   │       ├── gb-wls.svg
│   │   │   │       ├── gb.svg
│   │   │   │       ├── gd.svg
│   │   │   │       ├── ge.svg
│   │   │   │       ├── gf.svg
│   │   │   │       ├── gg.svg
│   │   │   │       ├── gh.svg
│   │   │   │       ├── gi.svg
│   │   │   │       ├── gl.svg
│   │   │   │       ├── gm.svg
│   │   │   │       ├── gn.svg
│   │   │   │       ├── gp.svg
│   │   │   │       ├── gq.svg
│   │   │   │       ├── gr.svg
│   │   │   │       ├── gs.svg
│   │   │   │       ├── gt.svg
│   │   │   │       ├── gu.svg
│   │   │   │       ├── gw.svg
│   │   │   │       ├── gy.svg
│   │   │   │       ├── hk.svg
│   │   │   │       ├── hm.svg
│   │   │   │       ├── hn.svg
│   │   │   │       ├── hr.svg
│   │   │   │       ├── ht.svg
│   │   │   │       ├── hu.svg
│   │   │   │       ├── id.svg
│   │   │   │       ├── ie.svg
│   │   │   │       ├── il.svg
│   │   │   │       ├── im.svg
│   │   │   │       ├── in.svg
│   │   │   │       ├── io.svg
│   │   │   │       ├── iq.svg
│   │   │   │       ├── ir.svg
│   │   │   │       ├── is.svg
│   │   │   │       ├── it.svg
│   │   │   │       ├── je.svg
│   │   │   │       ├── jm.svg
│   │   │   │       ├── jo.svg
│   │   │   │       ├── jp.svg
│   │   │   │       ├── ke.svg
│   │   │   │       ├── kg.svg
│   │   │   │       ├── kh.svg
│   │   │   │       ├── ki.svg
│   │   │   │       ├── km.svg
│   │   │   │       ├── kn.svg
│   │   │   │       ├── kp.svg
│   │   │   │       ├── kr.svg
│   │   │   │       ├── kw.svg
│   │   │   │       ├── ky.svg
│   │   │   │       ├── kz.svg
│   │   │   │       ├── la.svg
│   │   │   │       ├── lb.svg
│   │   │   │       ├── lc.svg
│   │   │   │       ├── li.svg
│   │   │   │       ├── lk.svg
│   │   │   │       ├── lr.svg
│   │   │   │       ├── ls.svg
│   │   │   │       ├── lt.svg
│   │   │   │       ├── lu.svg
│   │   │   │       ├── lv.svg
│   │   │   │       ├── ly.svg
│   │   │   │       ├── ma.svg
│   │   │   │       ├── mc.svg
│   │   │   │       ├── md.svg
│   │   │   │       ├── me.svg
│   │   │   │       ├── mf.svg
│   │   │   │       ├── mg.svg
│   │   │   │       ├── mh.svg
│   │   │   │       ├── mk.svg
│   │   │   │       ├── ml.svg
│   │   │   │       ├── mm.svg
│   │   │   │       ├── mn.svg
│   │   │   │       ├── mo.svg
│   │   │   │       ├── mp.svg
│   │   │   │       ├── mq.svg
│   │   │   │       ├── mr.svg
│   │   │   │       ├── ms.svg
│   │   │   │       ├── mt.svg
│   │   │   │       ├── mu.svg
│   │   │   │       ├── mv.svg
│   │   │   │       ├── mw.svg
│   │   │   │       ├── mx.svg
│   │   │   │       ├── my.svg
│   │   │   │       ├── mz.svg
│   │   │   │       ├── na.svg
│   │   │   │       ├── nc.svg
│   │   │   │       ├── ne.svg
│   │   │   │       ├── nf.svg
│   │   │   │       ├── ng.svg
│   │   │   │       ├── ni.svg
│   │   │   │       ├── nl.svg
│   │   │   │       ├── no.svg
│   │   │   │       ├── np.svg
│   │   │   │       ├── nr.svg
│   │   │   │       ├── nu.svg
│   │   │   │       ├── nz.svg
│   │   │   │       ├── om.svg
│   │   │   │       ├── pa.svg
│   │   │   │       ├── pe.svg
│   │   │   │       ├── pf.svg
│   │   │   │       ├── pg.svg
│   │   │   │       ├── ph.svg
│   │   │   │       ├── pk.svg
│   │   │   │       ├── pl.svg
│   │   │   │       ├── pm.svg
│   │   │   │       ├── pn.svg
│   │   │   │       ├── pr.svg
│   │   │   │       ├── ps.svg
│   │   │   │       ├── pt.svg
│   │   │   │       ├── pw.svg
│   │   │   │       ├── py.svg
│   │   │   │       ├── qa.svg
│   │   │   │       ├── re.svg
│   │   │   │       ├── ro.svg
│   │   │   │       ├── rs.svg
│   │   │   │       ├── ru.svg
│   │   │   │       ├── rw.svg
│   │   │   │       ├── sa.svg
│   │   │   │       ├── sb.svg
│   │   │   │       ├── sc.svg
│   │   │   │       ├── sd.svg
│   │   │   │       ├── se.svg
│   │   │   │       ├── sg.svg
│   │   │   │       ├── sh.svg
│   │   │   │       ├── si.svg
│   │   │   │       ├── sj.svg
│   │   │   │       ├── sk.svg
│   │   │   │       ├── sl.svg
│   │   │   │       ├── sm.svg
│   │   │   │       ├── sn.svg
│   │   │   │       ├── so.svg
│   │   │   │       ├── sr.svg
│   │   │   │       ├── ss.svg
│   │   │   │       ├── st.svg
│   │   │   │       ├── sv.svg
│   │   │   │       ├── sx.svg
│   │   │   │       ├── sy.svg
│   │   │   │       ├── sz.svg
│   │   │   │       ├── tc.svg
│   │   │   │       ├── td.svg
│   │   │   │       ├── tf.svg
│   │   │   │       ├── tg.svg
│   │   │   │       ├── th.svg
│   │   │   │       ├── tj.svg
│   │   │   │       ├── tk.svg
│   │   │   │       ├── tl.svg
│   │   │   │       ├── tm.svg
│   │   │   │       ├── tn.svg
│   │   │   │       ├── to.svg
│   │   │   │       ├── tr.svg
│   │   │   │       ├── tt.svg
│   │   │   │       ├── tv.svg
│   │   │   │       ├── tw.svg
│   │   │   │       ├── tz.svg
│   │   │   │       ├── ua.svg
│   │   │   │       ├── ug.svg
│   │   │   │       ├── um.svg
│   │   │   │       ├── us.svg
│   │   │   │       ├── uy.svg
│   │   │   │       ├── uz.svg
│   │   │   │       ├── va.svg
│   │   │   │       ├── vc.svg
│   │   │   │       ├── ve.svg
│   │   │   │       ├── vg.svg
│   │   │   │       ├── vi.svg
│   │   │   │       ├── vn.svg
│   │   │   │       ├── vu.svg
│   │   │   │       ├── wf.svg
│   │   │   │       ├── ws.svg
│   │   │   │       ├── ye.svg
│   │   │   │       ├── yt.svg
│   │   │   │       ├── za.svg
│   │   │   │       ├── zm.svg
│   │   │   │       ├── zw.svg
│   │   │   │       └── zz.svg
│   │   │   ├── LICENSE
│   │   │   ├── README.md
│   │   │   └── sass
│   │   │       ├── flag-icon-base.scss
│   │   │       ├── flag-icon-list.scss
│   │   │       ├── flag-icon-more.scss
│   │   │       ├── flag-icon.scss
│   │   │       └── variables.scss
│   │   ├── font-awesome
│   │   │   ├── attribution.js
│   │   │   ├── css
│   │   │   │   ├── all.css
│   │   │   │   ├── all.min.css
│   │   │   │   ├── brands.css
│   │   │   │   ├── brands.min.css
│   │   │   │   ├── duotone.css
│   │   │   │   ├── duotone.min.css
│   │   │   │   ├── fontawesome.css
│   │   │   │   ├── fontawesome.min.css
│   │   │   │   ├── light.css
│   │   │   │   ├── light.min.css
│   │   │   │   ├── regular.css
│   │   │   │   ├── regular.min.css
│   │   │   │   ├── solid.css
│   │   │   │   ├── solid.min.css
│   │   │   │   ├── svg-with-js.css
│   │   │   │   ├── svg-with-js.min.css
│   │   │   │   ├── thin.css
│   │   │   │   ├── thin.min.css
│   │   │   │   ├── v4-shims.css
│   │   │   │   └── v4-shims.min.css
│   │   │   ├── fonts
│   │   │   │   ├── fontawesome-webfont.eot
│   │   │   │   ├── fontawesome-webfont.svg
│   │   │   │   ├── fontawesome-webfont.ttf
│   │   │   │   ├── fontawesome-webfont.woff
│   │   │   │   ├── fontawesome-webfont.woff2
│   │   │   │   └── FontAwesome.otf
│   │   │   ├── js
│   │   │   │   └── fontawesome.min.js
│   │   │   ├── LICENSE.txt
│   │   │   └── webfonts
│   │   │       ├── fa-brands-400.ttf
│   │   │       ├── fa-brands-400.woff
│   │   │       ├── fa-brands-400.woff2
│   │   │       ├── fa-duotone-900.ttf
│   │   │       ├── fa-duotone-900.woff
│   │   │       ├── fa-duotone-900.woff2
│   │   │       ├── fa-light-300.ttf
│   │   │       ├── fa-light-300.woff
│   │   │       ├── fa-light-300.woff2
│   │   │       ├── fa-regular-400.ttf
│   │   │       ├── fa-regular-400.woff
│   │   │       ├── fa-regular-400.woff2
│   │   │       ├── fa-solid-900.ttf
│   │   │       ├── fa-solid-900.woff
│   │   │       ├── fa-solid-900.woff2
│   │   │       ├── fa-thin-100.ttf
│   │   │       ├── fa-thin-100.woff
│   │   │       └── fa-thin-100.woff2
│   │   ├── inter
│   │   │   ├── Inter-Black.ttf
│   │   │   ├── Inter-Bold.ttf
│   │   │   ├── Inter-ExtraBold.ttf
│   │   │   ├── Inter-ExtraLight.ttf
│   │   │   ├── Inter-Light.ttf
│   │   │   ├── Inter-Medium.ttf
│   │   │   ├── Inter-Regular.ttf
│   │   │   ├── Inter-SemiBold.ttf
│   │   │   └── Inter-Thin.ttf
│   │   ├── Montserrat
│   │   │   ├── Montserrat-Black.ttf
│   │   │   ├── Montserrat-BlackItalic.ttf
│   │   │   ├── Montserrat-Bold.ttf
│   │   │   ├── Montserrat-BoldItalic.ttf
│   │   │   ├── Montserrat-ExtraBold.ttf
│   │   │   ├── Montserrat-ExtraBoldItalic.ttf
│   │   │   ├── Montserrat-ExtraLight.ttf
│   │   │   ├── Montserrat-ExtraLightItalic.ttf
│   │   │   ├── Montserrat-Italic.ttf
│   │   │   ├── Montserrat-Light.ttf
│   │   │   ├── Montserrat-LightItalic.ttf
│   │   │   ├── Montserrat-Medium.ttf
│   │   │   ├── Montserrat-MediumItalic.ttf
│   │   │   ├── Montserrat-Regular.ttf
│   │   │   ├── Montserrat-SemiBold.ttf
│   │   │   ├── Montserrat-SemiBoldItalic.ttf
│   │   │   ├── Montserrat-Thin.ttf
│   │   │   ├── Montserrat-ThinItalic.ttf
│   │   │   └── OFL.txt
│   │   ├── Roboto
│   │   │   └── Roboto-Medium.ttf
│   │   └── roboto-mono
│   │       └── RobotoMono-Bold.ttf
│   ├── images
│   │   ├── (1).svg
│   │   ├── (2).svg
│   │   ├── 3-rounds.png
│   │   ├── ad-verify-error.svg
│   │   ├── admin
│   │   │   ├── admin-side-icon-2.svg
│   │   │   ├── admin-side-icon.svg
│   │   │   ├── everest-full-logo.png
│   │   │   ├── everest-half-logo.png
│   │   │   ├── google-icon.png
│   │   │   ├── infraon-logo-small.png
│   │   │   ├── key.png
│   │   │   ├── link.png
│   │   │   ├── visa.png
│   │   │   └── washing_machine.png
│   │   ├── ad_verify-error-icon.svg
│   │   ├── agent-installation-step1-mac-main.png
│   │   ├── agent-installation-step1-mac-main2.png
│   │   ├── agent-installation-step1-mac-main3.png
│   │   ├── agent-installation-step1-mac-main4.png
│   │   ├── agent-installation-step1-mac.png
│   │   ├── agent-installation-step1.png
│   │   ├── agent-installation-step2-mac.png
│   │   ├── agent-installation-step2.png
│   │   ├── agent-installation-step3-mac.png
│   │   ├── agent-installation-step3.png
│   │   ├── agent-installation-step4-mac.png
│   │   ├── agentdownload
│   │   │   ├── agent-installation-step1-mac-main.png
│   │   │   ├── agent-installation-step1-mac-main2.png.png
│   │   │   ├── agent-installation-step1-mac-main3.png
│   │   │   ├── agent-installation-step1-mac-main4.png
│   │   │   ├── data_agent_completed_step4.png
│   │   │   ├── data_agent_deployment_step1.png
│   │   │   ├── data_agent_manager_service_creation_step3.png
│   │   │   ├── data_agent_service_creation_step2.png
│   │   │   └── MicrosoftTeams-image (114) 3.png
│   │   ├── API
│   │   │   ├── AI.png
│   │   │   ├── excel.png
│   │   │   ├── figma.png
│   │   │   ├── intellij.png
│   │   │   ├── linux.png
│   │   │   ├── linux_B.png
│   │   │   ├── redhat.png
│   │   │   ├── sass.png
│   │   │   ├── vlc.png
│   │   │   ├── vscode.png
│   │   │   ├── windows-s.png
│   │   │   ├── windows.png
│   │   │   ├── windows_p.png
│   │   │   └── winrar.png
│   │   ├── asset
│   │   │   ├── asset.png
│   │   │   ├── barcode.png
│   │   │   ├── barcode.svg
│   │   │   ├── barcode2.svg
│   │   │   ├── battery.svg
│   │   │   ├── brand
│   │   │   │   ├── act.svg
│   │   │   │   ├── airtel.svg
│   │   │   │   ├── alphion.svg
│   │   │   │   ├── apple.svg
│   │   │   │   ├── aruba.svg
│   │   │   │   ├── bdcom.svg
│   │   │   │   ├── brocade.png
│   │   │   │   ├── bsnl.svg
│   │   │   │   ├── centos.svg
│   │   │   │   ├── check point.png
│   │   │   │   ├── check point.svg
│   │   │   │   ├── checkpoint.png
│   │   │   │   ├── checkpoint.svg
│   │   │   │   ├── cisco.svg
│   │   │   │   ├── citrix.svg
│   │   │   │   ├── d-link.svg
│   │   │   │   ├── debian.svg
│   │   │   │   ├── dell.svg
│   │   │   │   ├── dlink.jpg
│   │   │   │   ├── edgecore.svg
│   │   │   │   ├── F5.jpg
│   │   │   │   ├── f5.svg
│   │   │   │   ├── fedora.svg
│   │   │   │   ├── fortigate.svg
│   │   │   │   ├── Fortinet.png
│   │   │   │   ├── fortinet.svg
│   │   │   │   ├── fortios.svg
│   │   │   │   ├── foundry.png
│   │   │   │   ├── globe-pointer-light.svg
│   │   │   │   ├── google.svg
│   │   │   │   ├── hfcl.svg
│   │   │   │   ├── hp.svg
│   │   │   │   ├── huawei.svg
│   │   │   │   ├── jio.svg
│   │   │   │   ├── juniper.svg
│   │   │   │   ├── lenovo.svg
│   │   │   │   ├── lg.svg
│   │   │   │   ├── mac-logo.svg
│   │   │   │   ├── maipu.svg
│   │   │   │   ├── microsoft.svg
│   │   │   │   ├── nivetti.svg
│   │   │   │   ├── nokia.gif
│   │   │   │   ├── nokia.svg
│   │   │   │   ├── oracle.svg
│   │   │   │   ├── palo alto.svg
│   │   │   │   ├── radwin.svg
│   │   │   │   ├── redhat.svg
│   │   │   │   ├── rle.svg
│   │   │   │   ├── samsung.svg
│   │   │   │   ├── sify.svg
│   │   │   │   ├── solaris.svg
│   │   │   │   ├── sony.svg
│   │   │   │   ├── sophos.svg
│   │   │   │   ├── tata.svg
│   │   │   │   ├── tejas-networks-seeklogo.svg
│   │   │   │   ├── tejas.png
│   │   │   │   ├── tejas.svg
│   │   │   │   ├── ubuntu.png
│   │   │   │   ├── ubuntu.svg
│   │   │   │   ├── vmware.svg
│   │   │   │   ├── xerox.svg
│   │   │   │   ├── xiaomi.svg
│   │   │   │   ├── zte.jpg
│   │   │   │   └── zte.svg
│   │   │   ├── chart-area.svg
│   │   │   ├── Critical-red.svg
│   │   │   ├── critical.svg
│   │   │   ├── dark-scan-device.gif
│   │   │   ├── dark-scan-device_old.gif
│   │   │   ├── delete.svg
│   │   │   ├── flag.svg
│   │   │   ├── geomap
│   │   │   │   ├── firewall_green.svg
│   │   │   │   ├── firewall_grey.svg
│   │   │   │   ├── firewall_red.svg
│   │   │   │   ├── green.svg
│   │   │   │   ├── pointer_blue.svg
│   │   │   │   ├── pointer_green.svg
│   │   │   │   ├── pointer_grey.svg
│   │   │   │   ├── pointer_orange.svg
│   │   │   │   ├── pointer_red.svg
│   │   │   │   ├── red.svg
│   │   │   │   ├── router_green.svg
│   │   │   │   ├── router_grey.svg
│   │   │   │   ├── router_red.svg
│   │   │   │   ├── server_green.svg
│   │   │   │   ├── server_grey.svg
│   │   │   │   ├── server_red.svg
│   │   │   │   ├── site_green.png
│   │   │   │   ├── site_red.png
│   │   │   │   ├── switch_green.svg
│   │   │   │   ├── switch_grey.svg
│   │   │   │   ├── switch_red.svg
│   │   │   │   └── unknown.svg
│   │   │   ├── image.png
│   │   │   ├── Invoice.svg
│   │   │   ├── Invoice1.svg
│   │   │   ├── Invoice2.svg
│   │   │   ├── Invoice3.svg
│   │   │   ├── Invoice4.svg
│   │   │   ├── Invoice5.svg
│   │   │   ├── laptop.jpg
│   │   │   ├── like.svg
│   │   │   ├── link.svg
│   │   │   ├── Major-yellow.svg
│   │   │   ├── major.svg
│   │   │   ├── message.svg
│   │   │   ├── Minor-info.svg
│   │   │   ├── minor.svg
│   │   │   ├── more-vertical.svg
│   │   │   ├── nccm.svg
│   │   │   ├── os
│   │   │   │   ├── aix.svg
│   │   │   │   ├── android.svg
│   │   │   │   ├── arubaos.svg
│   │   │   │   ├── asa.svg
│   │   │   │   ├── big-ip.svg
│   │   │   │   ├── centos.svg
│   │   │   │   ├── ciscoios.svg
│   │   │   │   ├── comwareos.svg
│   │   │   │   ├── debian.svg
│   │   │   │   ├── debianos.svg
│   │   │   │   ├── dell.svg
│   │   │   │   ├── esxios.svg
│   │   │   │   ├── fedoraos.svg
│   │   │   │   ├── fmc.svg
│   │   │   │   ├── fortimanager.png
│   │   │   │   ├── fortimanager.svg
│   │   │   │   ├── fortios.png
│   │   │   │   ├── fortios.svg
│   │   │   │   ├── fxos.svg
│   │   │   │   ├── gaiaos.svg
│   │   │   │   ├── harmonyos.svg
│   │   │   │   ├── hypervos.svg
│   │   │   │   ├── ibmaix.svg
│   │   │   │   ├── ios.svg
│   │   │   │   ├── iosxe.svg
│   │   │   │   ├── iosxr.svg
│   │   │   │   ├── ironware.jpg
│   │   │   │   ├── junos.svg
│   │   │   │   ├── kvmos.svg
│   │   │   │   ├── linux.png
│   │   │   │   ├── linux.svg
│   │   │   │   ├── mac.png
│   │   │   │   ├── mac.svg
│   │   │   │   ├── MacOS.svg
│   │   │   │   ├── maipu.svg
│   │   │   │   ├── netscaleros.svg
│   │   │   │   ├── nios.svg
│   │   │   │   ├── nxos.svg
│   │   │   │   ├── oracle.svg
│   │   │   │   ├── oracleos.svg
│   │   │   │   ├── palo-alto.svg
│   │   │   │   ├── pan-os.svg
│   │   │   │   ├── procurve.png
│   │   │   │   ├── redhat.svg
│   │   │   │   ├── redhatos.svg
│   │   │   │   ├── screenos.svg
│   │   │   │   ├── sfos.svg
│   │   │   │   ├── solaris.svg
│   │   │   │   ├── solarisos.svg
│   │   │   │   ├── sros.svg
│   │   │   │   ├── suse.svg
│   │   │   │   ├── tejos.png
│   │   │   │   ├── tejos.svg
│   │   │   │   ├── tizen.svg
│   │   │   │   ├── ubuntu.png
│   │   │   │   ├── ubuntu.svg
│   │   │   │   ├── ubuntuos.svg
│   │   │   │   ├── unix.svg
│   │   │   │   ├── vmware.svg
│   │   │   │   ├── vrpos.svg
│   │   │   │   ├── windows.png
│   │   │   │   ├── windows.svg
│   │   │   │   ├── windowsos.svg
│   │   │   │   ├── xenserveros.svg
│   │   │   │   ├── zteos.jpg
│   │   │   │   ├── zteos.svg
│   │   │   │   ├── zxctn.svg
│   │   │   │   └── zxr10.svg
│   │   │   ├── panelview
│   │   │   │   ├── backplane_card.svg
│   │   │   │   ├── cef1_9p_card.svg
│   │   │   │   ├── cef1_card.svg
│   │   │   │   ├── dpu18_card.svg
│   │   │   │   ├── dpu8_card.svg
│   │   │   │   ├── ds1_card.svg
│   │   │   │   ├── empty_card.svg
│   │   │   │   ├── ftu20_card.svg
│   │   │   │   ├── ftu30p_card.svg
│   │   │   │   ├── nivetti
│   │   │   │   │   ├── 16-port-slot.svg
│   │   │   │   │   ├── 2-port-slot.svg
│   │   │   │   │   ├── 4-port-slot.svg
│   │   │   │   │   ├── 8-port-slot.svg
│   │   │   │   │   ├── controller.svg
│   │   │   │   │   ├── empty-slot.svg
│   │   │   │   │   ├── fan-empty-slot.svg
│   │   │   │   │   ├── fan.svg
│   │   │   │   │   ├── nrp_m_card.svg
│   │   │   │   │   ├── nrp_m_card_copper.svg
│   │   │   │   │   ├── nsp-2c24xges-c3h_card.svg
│   │   │   │   │   ├── NSP-2GEC8GE-I3P.svg
│   │   │   │   │   ├── power.svg
│   │   │   │   │   ├── standby-card.svg
│   │   │   │   │   ├── switch-card-a.svg
│   │   │   │   │   └── switch-card-b.svg
│   │   │   │   ├── portselectionplaceholder.png
│   │   │   │   ├── sot18_card.svg
│   │   │   │   ├── xa10g_card.svg
│   │   │   │   ├── xa20g_card.svg
│   │   │   │   └── xa60g_card.svg
│   │   │   ├── processor
│   │   │   │   ├── amd.svg
│   │   │   │   ├── intel.svg
│   │   │   │   ├── intelceleron.svg
│   │   │   │   ├── intelcore.svg
│   │   │   │   ├── inteli3.svg
│   │   │   │   ├── inteli5.svg
│   │   │   │   ├── inteli7.svg
│   │   │   │   ├── intelpentium.svg
│   │   │   │   ├── intelxeon.svg
│   │   │   │   ├── m1.svg
│   │   │   │   ├── m1max.svg
│   │   │   │   ├── m1pro.svg
│   │   │   │   ├── m1ultra.svg
│   │   │   │   ├── m2.svg
│   │   │   │   ├── ryzen5.svg
│   │   │   │   └── unknown.svg
│   │   │   ├── qrcode-1.png
│   │   │   ├── qrcode-2.svg
│   │   │   ├── qrcode.png
│   │   │   ├── scan-device.gif
│   │   │   ├── scan-device_old.gif
│   │   │   ├── search.svg
│   │   │   ├── sm-barcode.svg
│   │   │   ├── sm-qr-code.svg
│   │   │   ├── software
│   │   │   │   ├── Adobe reader.svg
│   │   │   │   ├── Anydesk.svg
│   │   │   │   ├── ARM.svg
│   │   │   │   ├── AVG AntiVirus.svg
│   │   │   │   ├── AWS.svg
│   │   │   │   ├── Backup and Sync from Google.svg
│   │   │   │   ├── Chrome.svg
│   │   │   │   ├── Cybreroam.svg
│   │   │   │   ├── Docker Desktop.svg
│   │   │   │   ├── Erlang.svg
│   │   │   │   ├── Figma.svg
│   │   │   │   ├── Filezilla.svg
│   │   │   │   ├── Firefox.svg
│   │   │   │   ├── Frame 6712.svg
│   │   │   │   ├── Frame 6713.svg
│   │   │   │   ├── Git.svg
│   │   │   │   ├── Google Drive.svg
│   │   │   │   ├── illustrator.svg
│   │   │   │   ├── image 63.svg
│   │   │   │   ├── Intel.svg
│   │   │   │   ├── intellij idea.svg
│   │   │   │   ├── Java.svg
│   │   │   │   ├── Kingsoft Office.svg
│   │   │   │   ├── Lenovo.svg
│   │   │   │   ├── Meld.svg
│   │   │   │   ├── Microsoft  Direct X.svg
│   │   │   │   ├── microsoft build.svg
│   │   │   │   ├── Microsoft Edge.svg
│   │   │   │   ├── Microsoft Silverlight.svg
│   │   │   │   ├── Microsoft Visual C++.svg
│   │   │   │   ├── Mongo DB.svg
│   │   │   │   ├── Ms access.svg
│   │   │   │   ├── Ms Excel.svg
│   │   │   │   ├── Ms powerpoint.svg
│   │   │   │   ├── Ms sql server.svg
│   │   │   │   ├── Ms teams.svg
│   │   │   │   ├── Ms word.svg
│   │   │   │   ├── NI Package.svg
│   │   │   │   ├── NI.svg
│   │   │   │   ├── Node JS.svg
│   │   │   │   ├── Notepad++.svg
│   │   │   │   ├── OpenSSL.svg
│   │   │   │   ├── pgadmin3.svg
│   │   │   │   ├── PostgreSQL.svg
│   │   │   │   ├── putty.svg
│   │   │   │   ├── Pycharm.svg
│   │   │   │   ├── Python.svg
│   │   │   │   ├── RabbitMQ.svg
│   │   │   │   ├── sass.svg
│   │   │   │   ├── Sophos SSL VPN.svg
│   │   │   │   ├── SSH Secure Shell.svg
│   │   │   │   ├── TeamViewer.svg
│   │   │   │   ├── TortoiseGit.svg
│   │   │   │   ├── Visa.svg
│   │   │   │   ├── vlc.svg
│   │   │   │   ├── Vmware.svg
│   │   │   │   ├── VS code.svg
│   │   │   │   ├── VS tools.svg
│   │   │   │   ├── Vulkan Run Time.svg
│   │   │   │   ├── Windows App.svg
│   │   │   │   ├── Windows PC Health Check.svg
│   │   │   │   ├── WinMerge.svg
│   │   │   │   ├── winpcap.svg
│   │   │   │   ├── Winrar.svg
│   │   │   │   ├── winscp.svg
│   │   │   │   └── Wireshark.svg
│   │   │   ├── syslog.svg
│   │   │   ├── thumbs-up-solid.svg
│   │   │   ├── thumbs-up.svg
│   │   │   ├── ticket.svg
│   │   │   ├── tick_success.svg
│   │   │   ├── type
│   │   │   │   ├── access-controller.svg
│   │   │   │   ├── access-points.svg
│   │   │   │   ├── accesscontroller.png
│   │   │   │   ├── accessories.svg
│   │   │   │   ├── accesspoint.png
│   │   │   │   ├── adaptersmultioutlets.svg
│   │   │   │   ├── airconditioner.svg
│   │   │   │   ├── award.svg
│   │   │   │   ├── battery.png
│   │   │   │   ├── board.svg
│   │   │   │   ├── book-stand.svg
│   │   │   │   ├── cctv.svg
│   │   │   │   ├── chair.svg
│   │   │   │   ├── chess-board.svg
│   │   │   │   ├── cleaner.svg
│   │   │   │   ├── clock-desk.svg
│   │   │   │   ├── cluster.svg
│   │   │   │   ├── cords.svg
│   │   │   │   ├── cupboard.svg
│   │   │   │   ├── default.svg
│   │   │   │   ├── desktop.png
│   │   │   │   ├── dustbin.svg
│   │   │   │   ├── electrical.svg
│   │   │   │   ├── electronics.svg
│   │   │   │   ├── fan.svg
│   │   │   │   ├── firewall.png
│   │   │   │   ├── furniture.svg
│   │   │   │   ├── game.svg
│   │   │   │   ├── group-29.png
│   │   │   │   ├── harddrive.png
│   │   │   │   ├── headphone.png
│   │   │   │   ├── host.svg
│   │   │   │   ├── ipad.svg
│   │   │   │   ├── kettle.svg
│   │   │   │   ├── keyboard.png
│   │   │   │   ├── laptop.png
│   │   │   │   ├── laptopaccessories.svg
│   │   │   │   ├── lightbulb.svg
│   │   │   │   ├── meetingroom.svg
│   │   │   │   ├── microphone.svg
│   │   │   │   ├── microwave-oven.svg
│   │   │   │   ├── mobile.svg
│   │   │   │   ├── monitor.png
│   │   │   │   ├── monitoraccessories.svg
│   │   │   │   ├── mouse.png
│   │   │   │   ├── olt.png
│   │   │   │   ├── ont.png
│   │   │   │   ├── other.png
│   │   │   │   ├── plants.svg
│   │   │   │   ├── printer.png
│   │   │   │   ├── projector-screen.svg
│   │   │   │   ├── projector.svg
│   │   │   │   ├── radio_unit.svg
│   │   │   │   ├── remotes.svg
│   │   │   │   ├── router.png
│   │   │   │   ├── sanitizer-stand.svg
│   │   │   │   ├── scanner.svg
│   │   │   │   ├── screens.svg
│   │   │   │   ├── sensor_device.svg
│   │   │   │   ├── server.png
│   │   │   │   ├── speaker.png
│   │   │   │   ├── subscriber_unit.svg
│   │   │   │   ├── switch.png
│   │   │   │   ├── table.svg
│   │   │   │   ├── tablet.png
│   │   │   │   ├── telephone.svg
│   │   │   │   ├── trash.svg
│   │   │   │   ├── tv.svg
│   │   │   │   ├── unidentified.svg
│   │   │   │   ├── unknown.png
│   │   │   │   ├── unknown.svg
│   │   │   │   ├── vacuum-cleaner.svg
│   │   │   │   ├── vending-machine.svg
│   │   │   │   ├── video-phone.svg
│   │   │   │   ├── virtual-machines-running.svg
│   │   │   │   ├── virtual-machines.svg
│   │   │   │   ├── vm-template.svg
│   │   │   │   ├── water-dispenser.svg
│   │   │   │   └── white-board-stand.svg
│   │   │   ├── Union.svg
│   │   │   └── view
│   │   │       ├── chart_network.svg
│   │   │       ├── checklist.svg
│   │   │       ├── clock.svg
│   │   │       ├── code.svg
│   │   │       ├── code_branch.svg
│   │   │       ├── dashboard.svg
│   │   │       ├── desktop.svg
│   │   │       ├── folder-gear-light.svg
│   │   │       ├── grid.svg
│   │   │       ├── harddrive.svg
│   │   │       ├── hardware_inventory.svg
│   │   │       ├── info_circle.svg
│   │   │       ├── interface.svg
│   │   │       ├── inventory_tree.svg
│   │   │       ├── jira.svg
│   │   │       ├── notification.svg
│   │   │       ├── port_utilization.svg
│   │   │       ├── recycle.svg
│   │   │       ├── sitemap.svg
│   │   │       ├── spanner.svg
│   │   │       ├── summary.svg
│   │   │       └── ticket.svg
│   │   ├── asset-login-sidepanel-dynamic-logo.svg
│   │   ├── asset-login-sidepanel.svg
│   │   ├── auth-bottom-bg.svg
│   │   ├── avatars
│   │   │   ├── 1-small.png
│   │   │   ├── 1.jpg
│   │   │   ├── 1.png
│   │   │   ├── 10-small.png
│   │   │   ├── 10.png
│   │   │   ├── 11-small.png
│   │   │   ├── 11.png
│   │   │   ├── 12-small.png
│   │   │   ├── 12.png
│   │   │   ├── 2-small.png
│   │   │   ├── 2.jpg
│   │   │   ├── 2.png
│   │   │   ├── 3-small.png
│   │   │   ├── 3.jpg
│   │   │   ├── 3.png
│   │   │   ├── 4-small.png
│   │   │   ├── 4.jpg
│   │   │   ├── 4.png
│   │   │   ├── 5-small.png
│   │   │   ├── 5.jpg
│   │   │   ├── 5.png
│   │   │   ├── 6-small.png
│   │   │   ├── 6.png
│   │   │   ├── 7-small.png
│   │   │   ├── 7.png
│   │   │   ├── 8-small.png
│   │   │   ├── 8.png
│   │   │   ├── 9-small.png
│   │   │   ├── 9.png
│   │   │   ├── avatar-2.png
│   │   │   └── avatar.png
│   │   ├── backgrounds
│   │   │   ├── chat-bg.svg
│   │   │   └── infibot_infraon.svg
│   │   ├── banner
│   │   │   ├── banner-1.jpg
│   │   │   ├── banner-10.jpg
│   │   │   ├── banner-11.jpg
│   │   │   ├── banner-12.jpg
│   │   │   ├── banner-13.jpg
│   │   │   ├── banner-14.jpg
│   │   │   ├── banner-15.jpg
│   │   │   ├── banner-16.jpg
│   │   │   ├── banner-17.jpg
│   │   │   ├── banner-18.jpg
│   │   │   ├── banner-19.jpg
│   │   │   ├── banner-2.jpg
│   │   │   ├── banner-20.jpg
│   │   │   ├── banner-21.jpg
│   │   │   ├── banner-22.jpg
│   │   │   ├── banner-23.jpg
│   │   │   ├── banner-24.jpg
│   │   │   ├── banner-25.jpg
│   │   │   ├── banner-26.jpg
│   │   │   ├── banner-27.jpg
│   │   │   ├── banner-28.jpg
│   │   │   ├── banner-29.jpg
│   │   │   ├── banner-3.jpg
│   │   │   ├── banner-30.jpg
│   │   │   ├── banner-31.jpg
│   │   │   ├── banner-32.jpg
│   │   │   ├── banner-33.jpg
│   │   │   ├── banner-34.jpg
│   │   │   ├── banner-35.jpg
│   │   │   ├── banner-36.jpg
│   │   │   ├── banner-37.jpg
│   │   │   ├── banner-38.jpg
│   │   │   ├── banner-39.jpg
│   │   │   ├── banner-4.jpg
│   │   │   ├── banner-40.jpg
│   │   │   ├── banner-5.jpg
│   │   │   ├── banner-6.jpg
│   │   │   ├── banner-7.jpg
│   │   │   ├── banner-8.jpg
│   │   │   ├── banner-9.jpg
│   │   │   ├── banner.png
│   │   │   └── parallax-4.jpg
│   │   ├── barcode.png
│   │   ├── barcodeassets.svg
│   │   ├── blue.png
│   │   ├── bots-configuration
│   │   │   ├── finance-assistance.svg
│   │   │   ├── hr-assistance.svg
│   │   │   ├── infi-bot-logo.svg
│   │   │   ├── it-assistance.svg
│   │   │   ├── legal-assistance.svg
│   │   │   ├── no-chart-image.svg
│   │   │   ├── ops-assistant.svg
│   │   │   ├── PDF.svg
│   │   │   └── women-safety-assistance.svg
│   │   ├── ci-relation
│   │   │   ├── department.svg
│   │   │   ├── location.svg
│   │   │   ├── requester.svg
│   │   │   └── user.svg
│   │   ├── content
│   │   │   ├── amazon-logo.jpg
│   │   │   ├── flowers-pieces
│   │   │   │   ├── 1.png
│   │   │   │   ├── 2.png
│   │   │   │   ├── 3.png
│   │   │   │   ├── 4.png
│   │   │   │   ├── 5.png
│   │   │   │   ├── 6.png
│   │   │   │   ├── 7.png
│   │   │   │   ├── 8.png
│   │   │   │   └── 9.png
│   │   │   ├── flowers.jpg
│   │   │   ├── hands.png
│   │   │   ├── jacket.jpg
│   │   │   ├── photos
│   │   │   │   ├── 1.jpeg
│   │   │   │   ├── 2.jpeg
│   │   │   │   ├── 3.jpeg
│   │   │   │   ├── 4.jpeg
│   │   │   │   ├── 5.jpeg
│   │   │   │   ├── 6.jpeg
│   │   │   │   └── 7.jpg
│   │   │   └── stars.jpg
│   │   ├── csat
│   │   │   ├── link-expired.svg
│   │   │   └── rating-bg.svg
│   │   ├── dashboard
│   │   │   └── thumbnails
│   │   │       ├── bar.png
│   │   │       ├── config_presentation.svg
│   │   │       ├── count-panel.svg
│   │   │       ├── device-status-summary.svg
│   │   │       ├── geo.png
│   │   │       ├── interface-down-panel.svg
│   │   │       ├── line.svg
│   │   │       ├── link-down-panel.svg
│   │   │       ├── network-diagram.svg
│   │   │       ├── pie.svg
│   │   │       ├── site-down-panel.svg
│   │   │       ├── status-summary.png
│   │   │       ├── summary.svg
│   │   │       ├── text-panel.svg
│   │   │       └── topology-panel.svg
│   │   ├── decore-left.svg
│   │   ├── decore-right.svg
│   │   ├── default-sidepanel.svg
│   │   ├── device-template
│   │   │   ├── computer.png
│   │   │   ├── Computer.svg
│   │   │   ├── laptops.svg
│   │   │   ├── network.png
│   │   │   ├── network.svg
│   │   │   ├── server.svg
│   │   │   ├── settings.png
│   │   │   ├── settings.svg
│   │   │   ├── shield.svg
│   │   │   └── vector.png
│   │   ├── drilldown
│   │   │   ├── hp.png
│   │   │   ├── icon-1.png
│   │   │   ├── icon-2.png
│   │   │   ├── icon-3.png
│   │   │   ├── icon-4.png
│   │   │   ├── icon-5.png
│   │   │   └── icon-6.png
│   │   ├── dynamic-form
│   │   │   ├── one-col.png
│   │   │   └── two-col.png
│   │   ├── empty-notification (2).svg
│   │   ├── empty-notification.svg
│   │   ├── empty-requester.svg
│   │   ├── error.gif
│   │   ├── everestims-log.svg
│   │   ├── explore-product-vector.svg
│   │   ├── face-smile-light.svg
│   │   ├── flip-horizontal.png
│   │   ├── flip-vertical.png
│   │   ├── getting-started
│   │   │   ├── Close.svg
│   │   │   ├── color-picker.png
│   │   │   ├── exclamation-light.svg
│   │   │   └── report-template.png
│   │   ├── gmail-img.svg
│   │   ├── green.png
│   │   ├── grey.png
│   │   ├── gSuite-img.svg
│   │   ├── helpdesk-sidepanel-dynamic-logo.svg
│   │   ├── helpdesk-sidepanel.svg
│   │   ├── helpdeskside.svg
│   │   ├── ico
│   │   │   └── favicon.ico
│   │   ├── icons
│   │   │   ├── angular.svg
│   │   │   ├── apple-safari.png
│   │   │   ├── apple-vector.png
│   │   │   ├── arrow-down-light.svg
│   │   │   ├── arrow-up-light.svg
│   │   │   ├── book.svg
│   │   │   ├── bootstrap.svg
│   │   │   ├── brush.svg
│   │   │   ├── check-circle.svg
│   │   │   ├── check-default.svg
│   │   │   ├── checked-round.svg
│   │   │   ├── configuration-folder.svg
│   │   │   ├── doc.png
│   │   │   ├── drive.png
│   │   │   ├── dropbox.png
│   │   │   ├── enter.png
│   │   │   ├── everestIMS-logo.svg
│   │   │   ├── figma.svg
│   │   │   ├── file-icons
│   │   │   │   ├── doc.png
│   │   │   │   ├── onedrive (1).png
│   │   │   │   ├── pdf.png
│   │   │   │   ├── psd.png
│   │   │   │   └── sketch.png
│   │   │   ├── google-chrome.png
│   │   │   ├── google.svg
│   │   │   ├── hand.png
│   │   │   ├── hand.svg
│   │   │   ├── icloud-1.png
│   │   │   ├── icloud.png
│   │   │   ├── icon_link.svg
│   │   │   ├── Image.png
│   │   │   ├── incidentview.png
│   │   │   ├── Infi_bot_outline.svg
│   │   │   ├── interaction.svg
│   │   │   ├── internet-explorer.png
│   │   │   ├── internet.png
│   │   │   ├── jpg.png
│   │   │   ├── js.png
│   │   │   ├── json.png
│   │   │   ├── left-arrow.svg
│   │   │   ├── linkdin.svg
│   │   │   ├── mozila-firefox.png
│   │   │   ├── netwrok.svg
│   │   │   ├── onedrive.png
│   │   │   ├── onedrivenew.png
│   │   │   ├── opera.png
│   │   │   ├── os-vector.png
│   │   │   ├── parachute.svg
│   │   │   ├── pdf.png
│   │   │   ├── psd.png
│   │   │   ├── react.svg
│   │   │   ├── report.png
│   │   │   ├── Review_Icon.svg
│   │   │   ├── rocket.svg
│   │   │   ├── search.svg
│   │   │   ├── sketch.png
│   │   │   ├── speaker.svg
│   │   │   ├── star.svg
│   │   │   ├── teams.svg
│   │   │   ├── ticket-primary.svg
│   │   │   ├── ticket.png
│   │   │   ├── ticket.svg
│   │   │   ├── toolbox.svg
│   │   │   ├── txt.png
│   │   │   ├── unknown.png
│   │   │   ├── vuejs.svg
│   │   │   └── xls.png
│   │   ├── illustration
│   │   │   ├── api.svg
│   │   │   ├── badge.svg
│   │   │   ├── demand.svg
│   │   │   ├── email.svg
│   │   │   ├── faq-illustrations.svg
│   │   │   ├── marketing.svg
│   │   │   ├── personalization.svg
│   │   │   ├── Pot1.svg
│   │   │   ├── Pot2.svg
│   │   │   ├── Pot3.svg
│   │   │   ├── pricing-Illustration.svg
│   │   │   └── sales.svg
│   │   ├── image-light.svg
│   │   ├── inactive
│   │   │   ├── cat-gif
│   │   │   ├── inactive-bg-img-1.svg
│   │   │   ├── inactive-bg-img-2.svg
│   │   │   ├── inactive-bg-img-3.svg
│   │   │   ├── inactive-bg-img-4.svg
│   │   │   └── inactive-cat.gif
│   │   ├── incident
│   │   │   ├── files_empty_state.svg
│   │   │   └── washing_machine.png
│   │   ├── incident-edit.svg
│   │   ├── india-flag.svg
│   │   ├── infi-bot-icon-sm.png
│   │   ├── infi-box-chat-icon.png
│   │   ├── infraon Logo.svg
│   │   ├── infraon Logo_Light.svg
│   │   ├── infraon-admin-logo.svg
│   │   ├── infraon-icon.svg
│   │   ├── infraon-integraton
│   │   │   ├── adobe-reader.png
│   │   │   ├── anydesk.png
│   │   │   ├── chrome.png
│   │   │   ├── infraon-integration-banner-image-old.png
│   │   │   ├── infraon-integration-banner-image.png
│   │   │   ├── ms-teams.png
│   │   │   ├── Notepad++.png
│   │   │   ├── pgadmin.png
│   │   │   ├── screen-shots
│   │   │   │   ├── screenshot-1.png
│   │   │   │   ├── screenshot-2.png
│   │   │   │   ├── screenshot-3.png
│   │   │   │   ├── screenshot-4.png
│   │   │   │   ├── screenshot-5.png
│   │   │   │   └── screenshot-6.png
│   │   │   ├── success-animation-json.json
│   │   │   └── success-animation.gif
│   │   ├── infraon-logo-Icon.svg
│   │   ├── infraon-logo.svg
│   │   ├── infraon-product-logo.svg
│   │   ├── infraonlogo.svg
│   │   ├── infraon_loading.gif
│   │   ├── infraon_logo.svg
│   │   ├── infraon_logoDNS.svg
│   │   ├── infraon_logoDNS_white.svg
│   │   ├── infraon_logo_icon.svg
│   │   ├── itsm-login-sidepanel-dynamic-logo.svg
│   │   ├── itsm-sidepanel.svg
│   │   ├── kb
│   │   │   ├── banner.png
│   │   │   ├── blog-img1.png
│   │   │   ├── blog-img2.png
│   │   │   └── ransomware-infographic.jpg
│   │   ├── lenovo.jpg
│   │   ├── loading_icon.png
│   │   ├── login-footer-bg.svg
│   │   ├── login.svg
│   │   ├── loginAsset.svg
│   │   ├── loginitsm.svg
│   │   ├── login_frame_1.png
│   │   ├── login_frame_2.png
│   │   ├── login_frame_3.png
│   │   ├── login_sidepanel_content.svg
│   │   ├── login_sidepanel_icon.svg
│   │   ├── logo
│   │   │   ├── favicon.ico
│   │   │   ├── infraon-Logo-square.svg
│   │   │   ├── infraon_logo-white.svg
│   │   │   ├── logo.png
│   │   │   └── logo.svg
│   │   ├── logo.gif
│   │   ├── logo.svg
│   │   ├── logo_icon.png
│   │   ├── lotty
│   │   │   ├── asset.json
│   │   │   ├── book.json
│   │   │   ├── change.json
│   │   │   ├── contract.json
│   │   │   ├── dashboard.json
│   │   │   ├── exclamation.json
│   │   │   ├── geomap.json
│   │   │   ├── getting-started.json
│   │   │   ├── home.json
│   │   │   ├── imacd.json
│   │   │   ├── marketplace.json
│   │   │   ├── nccm.json
│   │   │   ├── network.json
│   │   │   ├── notification.json
│   │   │   ├── plus.json
│   │   │   ├── problem.json
│   │   │   ├── purchaseorder.json
│   │   │   ├── question.json
│   │   │   ├── release-manage.json
│   │   │   ├── report-file.json
│   │   │   ├── request.json
│   │   │   ├── search.json
│   │   │   ├── service.json
│   │   │   ├── settings.json
│   │   │   ├── sla.json
│   │   │   ├── tasks.json
│   │   │   ├── ticket.json
│   │   │   ├── topology.json
│   │   │   └── workspace.json
│   │   ├── MacOS.svg
│   │   ├── marketplace
│   │   │   ├── adobe-reader.png
│   │   │   ├── anydesk.png
│   │   │   ├── chrome.png
│   │   │   ├── infraon
│   │   │   │   ├── azureAD.svg
│   │   │   │   ├── dell.png
│   │   │   │   ├── google_chat.png
│   │   │   │   ├── jamf.svg
│   │   │   │   ├── jira.svg
│   │   │   │   ├── ldap.png
│   │   │   │   ├── ms-teams.png
│   │   │   │   ├── RingCentral.svg
│   │   │   │   ├── service-now.svg
│   │   │   │   ├── slack.png
│   │   │   │   └── WhatsApp.png
│   │   │   ├── infraon-integration-banner-image-old.png
│   │   │   ├── infraon-integration-banner-image.png
│   │   │   ├── jamf.svg
│   │   │   ├── ms-teams.png
│   │   │   ├── Notepad++.png
│   │   │   ├── pgadmin.png
│   │   │   ├── screen-shots
│   │   │   │   ├── azure
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   ├── screenshot-2.png
│   │   │   │   │   ├── screenshot-3.png
│   │   │   │   │   ├── screenshot-4.png
│   │   │   │   │   └── screenshot-5.png
│   │   │   │   ├── dell
│   │   │   │   │   └── Screenshot-0.png
│   │   │   │   ├── googleworkspace
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   ├── screenshot-2.png
│   │   │   │   │   └── screenshot-3.png
│   │   │   │   ├── jamf
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   ├── screenshot-2.png
│   │   │   │   │   └── screenshot-3.png
│   │   │   │   ├── jira
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   ├── screenshot-2.png
│   │   │   │   │   ├── screenshot-3.png
│   │   │   │   │   ├── screenshot-4.png
│   │   │   │   │   ├── screenshot-5.png
│   │   │   │   │   └── screenshot-6.png
│   │   │   │   ├── ldap
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   ├── screenshot-2.png
│   │   │   │   │   ├── screenshot-3.png
│   │   │   │   │   ├── screenshot-4.png
│   │   │   │   │   └── screenshot-5.png
│   │   │   │   ├── ringcentral
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   ├── screenshot-2.png
│   │   │   │   │   ├── screenshot-3.png
│   │   │   │   │   └── screenshot-4.png
│   │   │   │   ├── screenshot-0.png
│   │   │   │   ├── screenshot-1.png
│   │   │   │   ├── screenshot-2.png
│   │   │   │   ├── screenshot-3.png
│   │   │   │   ├── screenshot-4.png
│   │   │   │   ├── screenshot-5.png
│   │   │   │   ├── servicenow
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   └── screenshot-2.png
│   │   │   │   ├── slack
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   ├── screenshot-2.png
│   │   │   │   │   ├── screenshot-3.png
│   │   │   │   │   ├── screenshot-4.png
│   │   │   │   │   └── screenshot-5.png
│   │   │   │   ├── teams
│   │   │   │   │   ├── application_secret.png
│   │   │   │   │   ├── bot_id.png
│   │   │   │   │   ├── bot_secret.png
│   │   │   │   │   ├── bot_service_name.png
│   │   │   │   │   ├── client_id.png
│   │   │   │   │   ├── resource_group.png
│   │   │   │   │   ├── screenshot-0.png
│   │   │   │   │   ├── screenshot-1.png
│   │   │   │   │   ├── screenshot-2.png
│   │   │   │   │   ├── screenshot-3.png
│   │   │   │   │   ├── screenshot-4.png
│   │   │   │   │   ├── screenshot-5.png
│   │   │   │   │   ├── screenshot-6.png
│   │   │   │   │   ├── screenshot-7.png
│   │   │   │   │   ├── screenshot-8.png
│   │   │   │   │   ├── subscription_id.png
│   │   │   │   │   └── tenant_id.png
│   │   │   │   └── whatsapp
│   │   │   │       ├── screenshot-0.png
│   │   │   │       ├── screenshot-1.png
│   │   │   │       ├── screenshot-2.png
│   │   │   │       ├── screenshot-3.png
│   │   │   │       ├── screenshot-4.png
│   │   │   │       ├── screenshot-5.png
│   │   │   │       └── secret_key.png
│   │   │   ├── slack.png
│   │   │   ├── success-animation-json.json
│   │   │   └── success-animation.gif
│   │   ├── misc
│   │   │   ├── leaf-green.png
│   │   │   ├── leaf-orange.png
│   │   │   ├── leaf-red.png
│   │   │   └── leaf-shadow.png
│   │   ├── msp
│   │   │   ├── image 21.svg
│   │   │   └── image 23.svg
│   │   ├── nivettilogo.jpg
│   │   ├── node.png
│   │   ├── notification
│   │   │   ├── content-image.svg
│   │   │   ├── footer-image-icon.svg
│   │   │   └── footer-image.svg
│   │   ├── no_license.svg
│   │   ├── office-img.svg
│   │   ├── ongc.png
│   │   ├── os
│   │   │   ├── linux.png
│   │   │   ├── mac.png
│   │   │   ├── oraclelinux.png
│   │   │   ├── redhat.png
│   │   │   └── windows.png
│   │   ├── other_mail.svg
│   │   ├── outlook-img.svg
│   │   ├── pages
│   │   │   ├── 1-apex.png
│   │   │   ├── 2-stack.png
│   │   │   ├── 3-convex.png
│   │   │   ├── 4-materialize.png
│   │   │   ├── 404.png
│   │   │   ├── 500.png
│   │   │   ├── arrow-down.png
│   │   │   ├── bgInvalid.svg
│   │   │   ├── bottomDesign.svg
│   │   │   ├── calendar-illustration.png
│   │   │   ├── card-image-4.jpg
│   │   │   ├── card-image-5.jpg
│   │   │   ├── card-image-6.jpg
│   │   │   ├── card-img-overlay.jpg
│   │   │   ├── cat.svg
│   │   │   ├── chat-bg.svg
│   │   │   ├── coming-soon-dark.svg
│   │   │   ├── coming-soon.svg
│   │   │   ├── content-img-1.jpg
│   │   │   ├── content-img-2.jpg
│   │   │   ├── content-img-3.jpg
│   │   │   ├── content-img-4.jpg
│   │   │   ├── eCommerce
│   │   │   │   ├── 1.png
│   │   │   │   ├── 10.png
│   │   │   │   ├── 11.png
│   │   │   │   ├── 12.png
│   │   │   │   ├── 13.png
│   │   │   │   ├── 14.png
│   │   │   │   ├── 15.png
│   │   │   │   ├── 16.png
│   │   │   │   ├── 17.png
│   │   │   │   ├── 18.png
│   │   │   │   ├── 19.png
│   │   │   │   ├── 2.png
│   │   │   │   ├── 20.png
│   │   │   │   ├── 21.png
│   │   │   │   ├── 22.png
│   │   │   │   ├── 23.png
│   │   │   │   ├── 24.png
│   │   │   │   ├── 25.png
│   │   │   │   ├── 26.png
│   │   │   │   ├── 27.png
│   │   │   │   ├── 3.png
│   │   │   │   ├── 4.png
│   │   │   │   ├── 5.png
│   │   │   │   ├── 6.png
│   │   │   │   ├── 7.png
│   │   │   │   ├── 8.png
│   │   │   │   ├── 9.png
│   │   │   │   ├── alienware-laptop.jpg
│   │   │   │   ├── amazon-chromecast.jpg
│   │   │   │   ├── amazon-echodot.jpg
│   │   │   │   ├── amazon-firestick.jpg
│   │   │   │   ├── amazon-google-home.jpg
│   │   │   │   ├── apple-ear-pods.jpg
│   │   │   │   ├── apple-Imac.jpg
│   │   │   │   ├── apple-macbook.jpg
│   │   │   │   ├── asus-desktop.jpg
│   │   │   │   ├── bank.png
│   │   │   │   ├── bower-and-wilkins-speaker.jpg
│   │   │   │   ├── canon-camera.jpg
│   │   │   │   ├── dell-inspirion.jpg
│   │   │   │   ├── garmin-watch.jpg
│   │   │   │   ├── garmin-watch2.jpg
│   │   │   │   ├── phillips-smart-led.jpg
│   │   │   │   ├── samsung-fridge.jpg
│   │   │   │   ├── sharp-50.jpg
│   │   │   │   ├── sony-75class-tv.jpg
│   │   │   │   └── sony-headphones.jpg
│   │   │   ├── error-dark.svg
│   │   │   ├── error.svg
│   │   │   ├── faq.jpg
│   │   │   ├── forgot-password-v2-dark.svg
│   │   │   ├── forgot-password-v2.svg
│   │   │   ├── forgot-password.png
│   │   │   ├── graphic-1.png
│   │   │   ├── graphic-2.png
│   │   │   ├── graphic-3.png
│   │   │   ├── graphic-4.png
│   │   │   ├── graphic-5.png
│   │   │   ├── graphic-6.png
│   │   │   ├── kb-article.jpg
│   │   │   ├── kb-image.jpg
│   │   │   ├── knowledge-base-cover.jpg
│   │   │   ├── lock-screen.png
│   │   │   ├── login
│   │   │   │   ├── facebook.svg
│   │   │   │   ├── github.svg
│   │   │   │   ├── google.svg
│   │   │   │   └── twitter.svg
│   │   │   ├── login-v2-dark.svg
│   │   │   ├── login-v2.svg
│   │   │   ├── login.png
│   │   │   ├── maintenance-2.png
│   │   │   ├── maintenance.png
│   │   │   ├── modern.jpg
│   │   │   ├── not-authorized-dark.svg
│   │   │   ├── not-authorized.png
│   │   │   ├── not-authorized.svg
│   │   │   ├── register-v2-dark.svg
│   │   │   ├── register-v2.svg
│   │   │   ├── register.jpg
│   │   │   ├── reset-password-v2-dark.svg
│   │   │   ├── reset-password-v2.svg
│   │   │   ├── reset-password.png
│   │   │   ├── rocket.png
│   │   │   ├── search-result.jpg
│   │   │   ├── TopDesign.svg
│   │   │   ├── under-maintenance-dark.svg
│   │   │   ├── under-maintenance.svg
│   │   │   ├── video-poster.jpg
│   │   │   └── vuexy-login-bg.jpg
│   │   ├── paper-plane-top-light.svg
│   │   ├── paperclip-light.svg
│   │   ├── pin-icon.png
│   │   ├── portrait
│   │   │   └── small
│   │   │       ├── avatar-s-1.jpg
│   │   │       ├── avatar-s-10.jpg
│   │   │       ├── avatar-s-11.jpg
│   │   │       ├── avatar-s-12.jpg
│   │   │       ├── avatar-s-13.jpg
│   │   │       ├── avatar-s-14.jpg
│   │   │       ├── avatar-s-15.jpg
│   │   │       ├── avatar-s-16.jpg
│   │   │       ├── avatar-s-17.jpg
│   │   │       ├── avatar-s-18.jpg
│   │   │       ├── avatar-s-19.jpg
│   │   │       ├── avatar-s-2.jpg
│   │   │       ├── avatar-s-20.jpg
│   │   │       ├── avatar-s-21.jpg
│   │   │       ├── avatar-s-22.jpg
│   │   │       ├── avatar-s-23.jpg
│   │   │       ├── avatar-s-24.jpg
│   │   │       ├── avatar-s-25.jpg
│   │   │       ├── avatar-s-26.jpg
│   │   │       ├── avatar-s-3.jpg
│   │   │       ├── avatar-s-4.jpg
│   │   │       ├── avatar-s-5.jpg
│   │   │       ├── avatar-s-6.jpg
│   │   │       ├── avatar-s-7.jpg
│   │   │       ├── avatar-s-8.jpg
│   │   │       └── avatar-s-9.jpg
│   │   ├── products
│   │   │   ├── 001.jpg
│   │   │   ├── 002.jpg
│   │   │   ├── 003.jpg
│   │   │   ├── 004.jpg
│   │   │   ├── infraon-product.svg
│   │   │   ├── product-asset.svg
│   │   │   ├── product-helpdesk.svg
│   │   │   ├── product-helpdesk2.svg
│   │   │   ├── product-infinity.svg
│   │   │   ├── product-itim.svg
│   │   │   ├── product-itsm.svg
│   │   │   ├── product-nms.svg
│   │   │   ├── product-oss.svg
│   │   │   ├── product-unms.svg
│   │   │   └── product-uptime.svg
│   │   ├── Profile Image backgruond.png
│   │   ├── profile_bg.png
│   │   ├── qrcode.png
│   │   ├── qrcode.png.png
│   │   ├── RDPScheduling
│   │   │   ├── active-icon.svg
│   │   │   ├── background-img.svg
│   │   │   ├── device-img.svg
│   │   │   ├── ended-icon.svg
│   │   │   ├── infraon-logo.svg
│   │   │   ├── time-counter.svg
│   │   │   └── upoming-icon.svg
│   │   ├── Rectangle-background-image.svg
│   │   ├── red.png
│   │   ├── reg-1.gif
│   │   ├── reg-2.gif
│   │   ├── reg-3.gif
│   │   ├── report
│   │   │   ├── csv-light.svg
│   │   │   ├── pdf-light.svg
│   │   │   └── xls-light.svg
│   │   ├── search
│   │   │   ├── arrow-down.png
│   │   │   ├── arrow-left.png
│   │   │   ├── arrow-right.png
│   │   │   ├── arrow-up.png
│   │   │   ├── book-open.png
│   │   │   ├── circle exclamation.png
│   │   │   ├── dashboard.png
│   │   │   ├── enter.png
│   │   │   ├── globe.png
│   │   │   ├── info.png
│   │   │   ├── notification.png
│   │   │   ├── plus.png
│   │   │   ├── report.png
│   │   │   ├── robot.png
│   │   │   ├── stopwatch.png
│   │   │   ├── tag.png
│   │   │   ├── ticket-dark.png
│   │   │   ├── ticket.png
│   │   │   ├── user-group.png
│   │   │   └── user.png
│   │   ├── self-service-banner.svg
│   │   ├── sign_in_ms.svg
│   │   ├── sla.svg
│   │   ├── SLA_icon.svg
│   │   ├── support_logo.svg
│   │   ├── svg
│   │   │   ├── calender.svg
│   │   │   ├── check.svg
│   │   │   ├── circle-img.svg
│   │   │   ├── datacenter-india.svg
│   │   │   ├── datacenter-location.svg
│   │   │   ├── datacenter-us.svg
│   │   │   ├── dot-dark-svg.svg
│   │   │   ├── dot-img.png
│   │   │   ├── dot-img.svg
│   │   │   ├── dot-svg.svg
│   │   │   ├── dot.svg
│   │   │   ├── dotted_bg.svg
│   │   │   ├── empty-state-dark.svg
│   │   │   ├── empty-state-light.svg
│   │   │   ├── India.svg
│   │   │   ├── outlook.svg
│   │   │   ├── pie-chart.svg
│   │   │   ├── Threshold.svg
│   │   │   └── tranceparent_bg.svg
│   │   ├── technical-catalogue
│   │   │   ├── default.png
│   │   │   ├── skeleton-keyfeature.svg
│   │   │   ├── skeleton-overview.svg
│   │   │   ├── step3.svg
│   │   │   ├── step4.svg
│   │   │   ├── step5.svg
│   │   │   └── step6.svg
│   │   ├── tf-logo.png
│   │   ├── tick.svg
│   │   ├── topology-node
│   │   │   ├── access_controller_blue.svg
│   │   │   ├── access_controller_green.svg
│   │   │   ├── access_controller_lightgray.svg
│   │   │   ├── access_controller_orange.svg
│   │   │   ├── access_controller_red.svg
│   │   │   ├── access_points_blue.svg
│   │   │   ├── access_points_green.svg
│   │   │   ├── access_points_lightgray.svg
│   │   │   ├── access_points_orange.svg
│   │   │   ├── access_points_red.svg
│   │   │   ├── default.svg
│   │   │   ├── deskotp_blue.svg
│   │   │   ├── deskotp_lightgray.svg
│   │   │   ├── deskotp_orange.svg
│   │   │   ├── deskotp_red.svg
│   │   │   ├── desktop_green.svg
│   │   │   ├── dwdm_green.svg
│   │   │   ├── firewall.svg
│   │   │   ├── firewall_blue.svg
│   │   │   ├── firewall_gray.svg
│   │   │   ├── firewall_green.svg
│   │   │   ├── firewall_lightgray.svg
│   │   │   ├── firewall_orange.svg
│   │   │   ├── firewall_red.svg
│   │   │   ├── firewall_yellow.svg
│   │   │   ├── green.svg
│   │   │   ├── l2switch_blue.svg
│   │   │   ├── l2switch_gray.svg
│   │   │   ├── l2switch_green.svg
│   │   │   ├── l2switch_orange.svg
│   │   │   ├── l2switch_red.svg
│   │   │   ├── l2switch_yellow.svg
│   │   │   ├── l3switch_blue.svg
│   │   │   ├── l3switch_gray.svg
│   │   │   ├── l3switch_green.svg
│   │   │   ├── l3switch_orange.svg
│   │   │   ├── l3switch_red.svg
│   │   │   ├── l3switch_yellow.svg
│   │   │   ├── laptop_blue.svg
│   │   │   ├── laptop_green.svg
│   │   │   ├── laptop_lightgray.svg
│   │   │   ├── laptop_orange.svg
│   │   │   ├── laptop_red.svg
│   │   │   ├── mux_green.svg
│   │   │   ├── mux_lightgray.svg
│   │   │   ├── mux_red.svg
│   │   │   ├── ng_sdh_green.svg
│   │   │   ├── orange.svg
│   │   │   ├── ping_blue.svg
│   │   │   ├── ping_green.svg
│   │   │   ├── ping_lightgray.svg
│   │   │   ├── ping_orange.svg
│   │   │   ├── ping_red.svg
│   │   │   ├── ptn_green.svg
│   │   │   ├── red.svg
│   │   │   ├── router.svg
│   │   │   ├── router_blue.svg
│   │   │   ├── router_gray.svg
│   │   │   ├── router_green.svg
│   │   │   ├── router_lightgray.svg
│   │   │   ├── router_orange.svg
│   │   │   ├── router_red.svg
│   │   │   ├── sdh.svg
│   │   │   ├── sdh_blue.svg
│   │   │   ├── sdh_gray.svg
│   │   │   ├── sdh_green.svg
│   │   │   ├── sdh_lightgray.svg
│   │   │   ├── sdh_orange.svg
│   │   │   ├── sdh_red.svg
│   │   │   ├── sdh_yellow.svg
│   │   │   ├── server.svg
│   │   │   ├── server_blue.svg
│   │   │   ├── server_green.svg
│   │   │   ├── server_lightgray.svg
│   │   │   ├── server_orange.svg
│   │   │   ├── server_red.svg
│   │   │   ├── switch.svg
│   │   │   ├── switch_blue.svg
│   │   │   ├── switch_gray.svg
│   │   │   ├── switch_green.svg
│   │   │   ├── switch_lightgray.svg
│   │   │   ├── switch_orange.svg
│   │   │   ├── switch_red.svg
│   │   │   ├── switch_yellow.svg
│   │   │   ├── ups.svg
│   │   │   ├── ups_blue.svg
│   │   │   ├── ups_gray.svg
│   │   │   ├── ups_green.svg
│   │   │   ├── ups_lightgray.svg
│   │   │   ├── ups_orange.svg
│   │   │   ├── ups_red.svg
│   │   │   └── ups_yellow.svg
│   │   ├── ubuntu 1.png
│   │   ├── ubuntu 2.png
│   │   ├── ubuntu 3.png
│   │   ├── user-chart.svg
│   │   ├── videoThumbnail.png
│   │   ├── workflow
│   │   │   ├── action.svg
│   │   │   ├── actionblue.svg
│   │   │   ├── actionorange.svg
│   │   │   ├── arrow.svg
│   │   │   ├── checkoff.svg
│   │   │   ├── checkon.svg
│   │   │   ├── close.svg
│   │   │   ├── closeleft.svg
│   │   │   ├── database.svg
│   │   │   ├── databaseorange.svg
│   │   │   ├── dropdown.svg
│   │   │   ├── error.svg
│   │   │   ├── errorblue.svg
│   │   │   ├── errorred.svg
│   │   │   ├── eye.svg
│   │   │   ├── eyeblue.svg
│   │   │   ├── grabme.svg
│   │   │   ├── heart.svg
│   │   │   ├── log.svg
│   │   │   ├── logred.svg
│   │   │   ├── meta.png
│   │   │   ├── more.svg
│   │   │   ├── search.svg
│   │   │   ├── tile.png
│   │   │   ├── time.svg
│   │   │   ├── timeblue.svg
│   │   │   ├── twitter.svg
│   │   │   └── twitterorange.svg
│   │   ├── workspace
│   │   │   ├── arrow-up-right-and-arrow-down-left-from-center-light.svg
│   │   │   ├── custom_field
│   │   │   │   └── dropdown_demo_img.png
│   │   │   ├── file-magnifying-glass-light.svg
│   │   │   ├── infi-logo-squre.svg
│   │   │   ├── infi-logo.svg
│   │   │   ├── infibot_infraon.svg
│   │   │   ├── infibot_infraon_1.svg
│   │   │   ├── infibot_infraon_dark.svg
│   │   │   ├── infibot_infraon_dark_1.svg
│   │   │   ├── list_img
│   │   │   │   ├── 1.png
│   │   │   │   ├── 10.png
│   │   │   │   ├── 11.png
│   │   │   │   ├── 12.png
│   │   │   │   ├── 13.png
│   │   │   │   ├── 14.png
│   │   │   │   ├── 15.png
│   │   │   │   ├── 16.png
│   │   │   │   ├── 17.png
│   │   │   │   ├── 18.png
│   │   │   │   ├── 19.png
│   │   │   │   ├── 2.png
│   │   │   │   ├── 20.png
│   │   │   │   ├── 21.png
│   │   │   │   ├── 22.png
│   │   │   │   ├── 23.png
│   │   │   │   ├── 24.png
│   │   │   │   ├── 25.png
│   │   │   │   ├── 26.png
│   │   │   │   ├── 27.png
│   │   │   │   ├── 28.png
│   │   │   │   ├── 29.png
│   │   │   │   ├── 3.png
│   │   │   │   ├── 30.png
│   │   │   │   ├── 31.png
│   │   │   │   ├── 32.png
│   │   │   │   ├── 33.png
│   │   │   │   ├── 34.png
│   │   │   │   ├── 35.png
│   │   │   │   ├── 36.png
│   │   │   │   ├── 4.png
│   │   │   │   ├── 5.png
│   │   │   │   ├── 6.png
│   │   │   │   ├── 7.png
│   │   │   │   ├── 8.png
│   │   │   │   └── 9.png
│   │   │   ├── no-card.svg
│   │   │   ├── no-filter-data-workspace-dark.svg
│   │   │   ├── no-filter-data-workspace.svg
│   │   │   └── png
│   │   │       ├── color.png
│   │   │       └── rocket.png
│   │   └── yellow.png
│   ├── js
│   │   └── chargebee.js
│   ├── json-response
│   │   ├── business-hour
│   │   │   ├── bzhr_delete_response.json
│   │   │   ├── bzhr_edit_response.json
│   │   │   ├── bzhr_holidayList.json
│   │   │   ├── bzhr_options_response.json
│   │   │   ├── bzhr_response.json
│   │   │   └── bzhr_save_response.json
│   │   ├── notify-rules
│   │   │   ├── trigger_list.json
│   │   │   └── trigger_options.json
│   │   ├── reports
│   │   │   ├── chart-type.json
│   │   │   ├── edit-response.json
│   │   │   ├── graph-data.json
│   │   │   ├── graphdata.json
│   │   │   ├── grid-data.json
│   │   │   ├── report-column-options.json
│   │   │   ├── report-option-response.json
│   │   │   ├── report-response.json
│   │   │   ├── report-stat-response.json
│   │   │   ├── report-type.json
│   │   │   └── tabledata.json
│   │   └── status.json
│   ├── scss
│   │   ├── styles.scss
│   │   └── variables
│   │       ├── _variables-components.scss
│   │       └── _variables.scss
│   └── vis
│       ├── css
│       │   └── vis-network.min.css
│       └── js
│           └── vis-network.min.js
├── environments
│   ├── environment.hmr.ts
│   ├── environment.instance.docker.ts
│   ├── environment.instance.ts
│   ├── environment.management.docker.ts
│   ├── environment.management.ts
│   ├── environment.prod.ts
│   └── environment.ts
├── favicon.ico
├── hmr.ts
├── index.html
├── karma.conf.js
├── main.ts
├── polyfills.ts
├── styles.scss
├── test.ts
├── tsconfig.app.json
├── tsconfig.spec.json
└── tslint.json

```