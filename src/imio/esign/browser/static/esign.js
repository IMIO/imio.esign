jQuery(function($) {
    $('a.esign-create-custom-session').prepOverlay({
        subtype: 'ajax',
        filter: '#content>*',
        formselector: '#form',
        closeselector: '[name="form.buttons.cancel"]',
        noform: function(el, pbo) {
            window.location.reload();
        }
    });

    // Add-to-custom-esign-session overlay (bound to actionspanel links)
    function initCustomSessionOverlays() {
        $('a.apButtonAction_form_add_to_custom_esign_session').each(function() {
            if ($(this).data('pbo') === undefined) {
                $(this).prepOverlay({
                    subtype: 'ajax',
                    filter: '#content>*',
                    formselector: '#add-to-custom-esign-session-form',
                    closeselector: '[name="form.buttons.cancel"]',
                    noform: function(el, pbo) {
                        window.location.reload();
                    }
                });
            }
        });
    }
    initCustomSessionOverlays();
    $(document).ajaxComplete(initCustomSessionOverlays);

    // Enable submit button when a radio session is selected
    function initSubmitToggle(container) {
        var $container = $(container || document);
        $container.find('#add-to-custom-esign-session-form input[name="session_id"]').on('change', function() {
            $(this).closest('form').find('#esign-submit-btn').prop('disabled', false);
        });
    }
    $(document).bind('loadInsideOverlay', function(e, el) { initSubmitToggle(el); });

    // After the choose-session overlay loads, bind the "Create new session"
    // link so it opens @@create-custom-session in a nested prepOverlay.
    // On successful creation, the outer overlay content is refetched and
    // the newest session is auto-selected.
    $(document).bind('loadInsideOverlay', function(e, el) {
        var $el = $(el);
        var $form = $el.find('#add-to-custom-esign-session-form');
        if (!$form.length) return;

        var sessionListUrl = $form.attr('action');
        var $pbAjax = $el.hasClass('pb-ajax') ? $el : $el.find('.pb-ajax');
        if (!$pbAjax.length) $pbAjax = $el;

        $el.find('a.esign-create-custom-session-from-overlay').each(function() {
            if ($(this).data('pbo') !== undefined) return;
            $(this).prepOverlay({
                subtype: 'ajax',
                filter: '#content>*',
                formselector: '#form',
                closeselector: '[name="form.buttons.cancel"]',
                noform: function(innerEl, innerPbo) {
                    // Session created. Refetch the session list into the
                    // outer overlay and auto-select the newest session.
                    $pbAjax.load(
                        sessionListUrl + '?ajax_load=' + (new Date().getTime()) + ' #content>*',
                        function() {
                            $pbAjax.find('input[name="session_id"]:first').prop('checked', true);
                            $pbAjax.find('#esign-submit-btn').prop('disabled', false);
                            // Re-initialise nested handlers inside the refreshed content
                            $(document).trigger('loadInsideOverlay', [el]);
                        }
                    );
                    return 'close';
                }
            });
        });
    });
});
