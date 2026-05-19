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
});
