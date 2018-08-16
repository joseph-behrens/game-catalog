function validateForm() {
    var image_text = document.getElementById('image_text');
    var image_url = document.getElementById('image_url');
    if (image_text.value.trim() == '' && image_url.value.trim() != '') {
        image_text_error.innerHTML = 'An image name is required to add an image';
        return false;
    }
    if (image_text.value.trim() != '' && image_url.value.trim() == '') {
        image_url_error.innerHTML = 'A url is required to add an image';
        return false;
    }
}

function showNewEntryFields(type) {
    document.getElementById(type + '_drop_down').style.display = "none";
    var new_section = document.getElementsByClassName('new_' + type);
    [].forEach.call(new_section, function(e){
        e.style.display = "block";
    });
}

function hideNewEntryFields(type) {
    document.getElementById(type + '_drop_down').style.display = "block";
    var new_section = document.getElementsByClassName('new_' + type);
    [].forEach.call(new_section, function(e){
        e.style.display = "none";
        for (var key in e.childNodes) {
            e.childNodes[key].value = "";
        }
    });
}